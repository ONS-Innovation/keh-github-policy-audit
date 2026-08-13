#!/bin/sh
set -eu

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Poetry installs under ~/.local/bin; expose it for subsequent scripts.
export PATH="${HOME:-/root}/.local/bin:${PATH}"

if ! command -v poetry >/dev/null 2>&1; then
	echo "Error: poetry not found in PATH after installation."
	exit 1
fi

cd resource-repo

# Build the dependency layer and Lambda functions
sh ./scripts/build-dependency-layer.sh
sh ./scripts/build-lambda-functions.sh
