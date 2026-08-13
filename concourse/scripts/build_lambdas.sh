#!/bin/sh
set -eu

cd resource-repo

sh ./scripts/build-dependency-layer.sh
sh ./scripts/build-lambda-functions.sh
