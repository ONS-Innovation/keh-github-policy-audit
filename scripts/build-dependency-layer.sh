#!/bin/sh
set -e

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
export LOG_CONTEXT="DEPENDENCY_LAYER"
# shellcheck source=scripts/lib/logging.sh
. "$SCRIPT_DIR/lib/logging.sh"

setup_error_trap "rm -rf ./tmp"

log_step "Building dependency layer"
log_info "Removing old build artifacts"

rm -rf ./tmp
rm -rf ./build

log_info "Creating build directories"

mkdir -p ./tmp/dependency-layer
mkdir -p ./build

log_info "Installing dependencies"

poetry run pip install --target ./tmp/dependency-layer --quiet .

log_info "Removing unnecessary files"

find ./tmp/dependency-layer -type d -name "__pycache__" -exec rm -rf {} +
find ./tmp/dependency-layer -type f -name "*.pyc" -delete
find ./tmp/dependency-layer -type f -name "*.pyo" -delete
find ./tmp/dependency-layer -type d -name "*.dist-info" -exec rm -rf {} +
find ./tmp/dependency-layer -type d -name "*.egg-info" -exec rm -rf {} +

log_info "Packaging dependencies"

zip -rq ./build/dependency-layer.zip ./tmp/dependency-layer

log_info "Cleaning up"

rm -rf ./tmp

clear_error_trap

log_done "Dependency layer build complete"
