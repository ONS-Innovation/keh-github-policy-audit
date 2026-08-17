#!/bin/sh
set -eu

apk add --no-cache jq

if [ -z "${secrets:-}" ]; then
	echo "Error: secrets is not set."
	exit 1
fi
if [ -z "${env:-}" ]; then
	echo "Error: env is not set."
	exit 1
fi

if [ -n "${github_access_token:-}" ]; then
	git config --global url."https://x-access-token:${github_access_token}@github.com/".insteadOf "https://github.com/"
else
	echo "Warning: github_access_token is not set; Terraform private Git module downloads may fail."
fi

required_keys='env_name region github_app_id_secret_name github_private_key_secret_name organisation_schedules'

for key in $required_keys; do
	if ! echo "$secrets" | jq -e --arg key "$key" '.[$key] != null and .[$key] != ""' >/dev/null; then
		echo "Error: required key '$key' is missing or empty in secrets."
		exit 1
	fi
done

if ! echo "$secrets" | jq -e '.organisation_schedules | type == "array" and length > 0' >/dev/null; then
	echo "Error: organisation_schedules must be a non-empty array in secrets."
	exit 1
fi

env_name=$(echo "$secrets" | jq -r '.env_name')
region=$(echo "$secrets" | jq -r '.region')
github_app_id_secret_name=$(echo "$secrets" | jq -r '.github_app_id_secret_name')
github_private_key_secret_name=$(echo "$secrets" | jq -r '.github_private_key_secret_name')
organisation_schedules=$(echo "$secrets" | jq -c '.organisation_schedules')
release_version="${tag:-manual}"

# Convert the organisation_schedules array into a Terraform-compatible HCL format
organisation_schedules_hcl=$(echo "$organisation_schedules" | jq -r '
	[.[] |
		"{ owner = " + (.owner | @json) +
		", schedule_expression = " + (.schedule_expression | @json) +
		(if (.dependabot_slo_levels // null) != null
			then ", dependabot_slo_levels = " + (.dependabot_slo_levels | tojson)
			else ""
		end) +
		" }"
	] | "[" + join(", ") + "]"
')

if [ "$env" != "prod" ]; then
	env="dev"
fi

echo "$env"

echo "Applying Terraform infrastructure"
cd resource-repo/terraform
terraform init -backend-config=env/"${env}"/backend-"${env}".tfbackend -reconfigure

terraform apply \
	-var "env_name=${env_name}" \
	-var "region=${region}" \
	-var "github_app_id_secret_name=${github_app_id_secret_name}" \
	-var "github_private_key_secret_name=${github_private_key_secret_name}" \
	-var "release_version=${release_version}" \
	-var "organisation_schedules=${organisation_schedules_hcl}" \
	-auto-approve
