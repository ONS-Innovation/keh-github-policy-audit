#!/bin/bash
# Run list_repositories followed by one or both organisation SLO checks locally.
#
# Usage:
#   ./scripts/run_organisation_slo_checks.sh --owner ONS-Innovation
#   ./scripts/run_organisation_slo_checks.sh --owner ONS-Innovation --run-id my-run
#   ./scripts/run_organisation_slo_checks.sh --owner ONS-Innovation --check dependabot
#   ./scripts/run_organisation_slo_checks.sh --owner ONS-Innovation --run-id my-run --use-existing-list
#
# GitHub credentials are resolved by the normal local AWS/GitHub configuration.

set -e

OWNER=""
RUN_ID=""
RUN_ID_SET=false
CHECK="all"
USE_EXISTING_LIST=false
LEVELS_JSON='["critical", "high", "medium", "low"]'

while [[ $# -gt 0 ]]; do
	case $1 in
	--owner)
		OWNER="$2"
		shift 2
		;;
	--run-id)
		RUN_ID="$2"
		RUN_ID_SET=true
		shift 2
		;;
	--check)
		CHECK="$2"
		shift 2
		;;
	--use-existing-list)
		USE_EXISTING_LIST=true
		shift
		;;
	--levels)
		LEVELS_JSON="$2"
		shift 2
		;;
	*)
		echo "Unknown option: $1" >&2
		exit 1
		;;
	esac
done

if [[ -z "$OWNER" ]]; then
	echo "Usage: $0 --owner OWNER [--run-id RUN_ID] [--check all|dependabot|secret-scanning] [--use-existing-list] [--levels '[]']" >&2
	exit 1
fi

if [[ "$USE_EXISTING_LIST" == true && "$RUN_ID_SET" == false ]]; then
	echo "--run-id is required when using --use-existing-list" >&2
	exit 1
fi

if [[ "$RUN_ID_SET" == false ]]; then
	RUN_ID="organisation-slo-checks"
fi

if [[ "$CHECK" != "all" && "$CHECK" != "dependabot" && "$CHECK" != "secret-scanning" ]]; then
	echo "Invalid check: $CHECK (choose all, dependabot, or secret-scanning)" >&2
	exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_OUTPUT_DIR="$SCRIPT_DIR/outputs/audit-runs/$OWNER/$RUN_ID"
REPOSITORY_OUTPUT_FILE="$REPOSITORY_OUTPUT_DIR/repositories-list.json"

EVENT_FILE=$(mktemp)
trap 'rm -f "$EVENT_FILE"' EXIT

export ENVIRONMENT=local

jq -n \
	--arg owner "$OWNER" \
	--arg run_id "$RUN_ID" \
	--argjson levels "$LEVELS_JSON" \
	'{owner: $owner, run_id: $run_id, levels: $levels}' >"$EVENT_FILE"

if [[ "$USE_EXISTING_LIST" == true ]]; then
	if [[ ! -f "$REPOSITORY_OUTPUT_FILE" ]]; then
		echo "Repository list not found: $REPOSITORY_OUTPUT_FILE" >&2
		exit 1
	fi

	if ! jq -e 'type == "array"' "$REPOSITORY_OUTPUT_FILE" >/dev/null; then
		echo "Repository list must contain a JSON array: $REPOSITORY_OUTPUT_FILE" >&2
		exit 1
	fi

	echo "Using existing repository list: $REPOSITORY_OUTPUT_FILE"
else
	echo "Running list_repositories for $OWNER with run_id=$RUN_ID"
	python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
		"functions.list_repositories.handler" \
		"$EVENT_FILE" \
		--event-file
fi

if [[ "$CHECK" == "all" || "$CHECK" == "dependabot" ]]; then
	echo "Running Dependabot SLO check"
	python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
		"functions.organisation_checks.dependabot_slo.handler" \
		"$EVENT_FILE" \
		--event-file
fi

if [[ "$CHECK" == "all" || "$CHECK" == "secret-scanning" ]]; then
	echo "Running Secret Scanning SLO check"
	python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
		"functions.organisation_checks.secret_scanning_slo.handler" \
		"$EVENT_FILE" \
		--event-file
fi

echo "Repository list used: $REPOSITORY_OUTPUT_FILE"
