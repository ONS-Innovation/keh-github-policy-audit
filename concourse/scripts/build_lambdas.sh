#!/bin/bash
set -eu

echo "Building Lambda functions and dependency layer..."

echo "Current directory: $(pwd)"

cd resource-repo

sh ./scripts/build-dependency-layer.sh
sh ./scripts/build-lambda-functions.sh