#!/bin/sh
set -eu

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

cd resource-repo

# Build the dependency layer and Lambda functions
sh ./scripts/build-dependency-layer.sh
sh ./scripts/build-lambda-functions.sh
