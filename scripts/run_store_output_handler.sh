#!/bin/bash
# This script runs the storage handlers that are normally invoked by Step Functions,
# allowing store_output to have data to read and aggregate. It uses example event files
# to simulate the typical workflow.
#
# Usage:
#   ./scripts/run_store_output_handler.sh
#   ./scripts/run_store_output_handler.sh --run-id custom-run-id

set -e

# Parse arguments
RUN_ID="run-store-output-handler"
while [[ $# -gt 0 ]]; do
    case $1 in
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Get workspace root (script is in scripts/, so go up one level)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLES_DIR="$SCRIPT_DIR/examples"

# Temporary directory for modified events
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Function to update run_id in a JSON file
update_run_id() {
    local input_file=$1
    local output_file=$2
    jq --arg run_id "$RUN_ID" '.run_id = $run_id' "$input_file" > "$output_file"
}

echo "Running storage handlers with run_id=$RUN_ID"

# Set environment to local for file-based operations
export ENVIRONMENT=local

# Prepare event files
echo "Loading example events..."
update_run_id "$EXAMPLES_DIR/store_organisation_checks_event.json" "$TEMP_DIR/org_event.json"
update_run_id "$EXAMPLES_DIR/store_repository_output_event.json" "$TEMP_DIR/repo_event.json"
update_run_id "$EXAMPLES_DIR/store_team_checks_event.json" "$TEMP_DIR/team_event.json"
update_run_id "$EXAMPLES_DIR/store_output_event.json" "$TEMP_DIR/output_event.json"

# Execute store_organisation_checks
echo "Executing store_organisation_checks..."
python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
    "functions.storage_functions.store_organisation_checks.handler" \
    "$TEMP_DIR/org_event.json" \
    --event-file

# Execute store_repository_output
echo "Executing store_repository_output..."
python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
    "functions.storage_functions.store_repository_output.handler" \
    "$TEMP_DIR/repo_event.json" \
    --event-file

# Execute store_team_checks
echo "Executing store_team_checks..."
python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
    "functions.storage_functions.store_team_checks.handler" \
    "$TEMP_DIR/team_event.json" \
    --event-file

# Execute store_output to aggregate the results
echo "Executing store_output to aggregate results..."
python "$SCRIPT_DIR/github_policy_audit/run_handler.py" \
    "functions.storage_functions.store_output.handler" \
    "$TEMP_DIR/output_event.json" \
    --event-file

OWNER=$(jq -r '.owner' "$TEMP_DIR/org_event.json")
echo "✅ All handlers executed successfully! Output stored in outputs/$OWNER/"
