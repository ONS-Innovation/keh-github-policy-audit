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

mkdir -p ./tmp/dependency-layer/python
mkdir -p ./build

log_info "Installing dependencies"

# Install policy library without deps (git source, pure Python package).
poetry run pip install --target ./tmp/dependency-layer/python --quiet --no-deps \
	"policy-methods-library @ git+https://github.com/ONS-Innovation/keh-policy-methods-library.git"

# Install runtime dependencies as Linux wheels for Lambda (x86_64, Python 3.12).
# This is needed when building on macOS or Windows. When building via Concourse, the build container is Linux, so this is not strictly necessary, but it doesn't hurt.
poetry run pip install --target ./tmp/dependency-layer/python --quiet \
	--platform manylinux2014_x86_64 \
	--implementation cp \
	--python-version 3.12 \
	--only-binary=:all: \
	"boto3>=1.43.40,<2.0.0" \
	"jwt>=1.4.0,<2.0.0" \
	"requests>=2.33.1,<3.0.0"

log_info "Removing unnecessary files"

find ./tmp/dependency-layer -type d -name "__pycache__" -exec rm -rf {} +
find ./tmp/dependency-layer -type f -name "*.pyc" -delete
find ./tmp/dependency-layer -type f -name "*.pyo" -delete
find ./tmp/dependency-layer -type d -name "*.dist-info" -exec rm -rf {} +
find ./tmp/dependency-layer -type d -name "*.egg-info" -exec rm -rf {} +

log_info "Packaging dependencies"

(
	cd ./tmp/dependency-layer
	zip -rq ../../build/dependency-layer.zip python
)

log_info "Cleaning up"

rm -rf ./tmp

clear_error_trap

log_done "Dependency layer build complete"
