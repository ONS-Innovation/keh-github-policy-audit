#!/bin/sh
set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
LOG_CONTEXT="LAMBDAS"
. "$SCRIPT_DIR/lib/logging.sh"

FUNCTIONS_DIR="$REPO_ROOT/github_policy_audit/functions"
UTILS_DIR="$REPO_ROOT/github_policy_audit/utils"
BUILD_DIR="$REPO_ROOT/build/lambdas"
TMP_DIR="$REPO_ROOT/tmp/lambdas"

setup_error_trap "rm -rf '$TMP_DIR'"

log_step "Building lambda function packages"
log_info "Removing old build artifacts"

rm -rf "$TMP_DIR"
rm -rf "$BUILD_DIR"

log_info "Creating build directories"

mkdir -p "$TMP_DIR"
mkdir -p "$BUILD_DIR"

handler_files=$(find "$FUNCTIONS_DIR" -type f -name "handler.py" | sort)

if [ -z "$handler_files" ]; then
	log_error "No handler.py files found under $FUNCTIONS_DIR"
	exit 1
fi

built_count=0

for handler_file in $handler_files; do
	relative_handler_path=${handler_file#"$FUNCTIONS_DIR"/}
	relative_function_dir=$(dirname "$relative_handler_path")
	zip_stem=$(printf '%s' "$relative_function_dir" | tr '/' '-')
	zip_path="$BUILD_DIR/$zip_stem.zip"
	lambda_tmp_dir="$TMP_DIR/$zip_stem"
	parent_dir=$(dirname "$relative_function_dir")

	log_info "Packaging $relative_function_dir -> build/lambdas/$zip_stem.zip"

	rm -rf "$lambda_tmp_dir"
	mkdir -p "$lambda_tmp_dir/functions"
	if [ "$parent_dir" != "." ]; then
		mkdir -p "$lambda_tmp_dir/functions/$parent_dir"
	fi

	cp -R "$FUNCTIONS_DIR/$relative_function_dir" "$lambda_tmp_dir/functions/$relative_function_dir"
	cp -R "$UTILS_DIR" "$lambda_tmp_dir/utils"

	find "$lambda_tmp_dir" -type d -name "__pycache__" -exec rm -rf {} +
	find "$lambda_tmp_dir" -type f -name "*.pyc" -delete
	find "$lambda_tmp_dir" -type f -name "*.pyo" -delete

	(
		cd "$lambda_tmp_dir"
		zip -rq "$zip_path" .
	)

	built_count=$((built_count + 1))
done

log_info "Cleaning up temporary files"
rm -rf "$TMP_DIR"

clear_error_trap

log_done "Built $built_count lambda packages in build/lambdas"
