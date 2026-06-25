.DEFAULT_GOAL := help

# The spacing and comments in this Makefile are intentionally formatted to
# allow the `make` command to display a nicely formatted list of available
# targets and their descriptions.

# Single hash symbols (#) are used for comments that are not displayed in
# the `make` output, while double hash symbols (##) are used for comments
# that are displayed when running `make` without any arguments or with the
# `make help` command.

# To add breaks between sections in the `make` output, simply add a comment line with
# double hash symbols and some spacing, as shown below.

## 
## -----------------------------------------------
## Makefile for [Project Name]
## -----------------------------------------------
## 

.PHONY: help
help:				## This help message.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

## 

.PHONY: clean
clean: 				## Clean the temporary files.
	rm -rf megalinter-reports
	rm -rf site

## 

# TODO: Add more targets as needed.

# MkDocs

.PHONY: docs-install
docs-install: 			## Install the dependencies for MkDocs.
	poetry install --only docs

.PHONY: docs-serve
docs-serve: docs-install 	## Serve the documentation locally.
	poetry run mkdocs serve

.PHONY: docs-build
docs-build: docs-install 	## Build the documentation.
	poetry run mkdocs build --site-dir site

.PHONY: docs-lint
docs-lint: 			## Install and run the documentation linter (Markdownlint).
	npm install -g markdownlint-cli
	markdownlint .

.PHONY: docs-fix
docs-fix: 			## Install and run the documentation linter with auto-fix (Markdownlint).
	npm install -g markdownlint-cli
	markdownlint . --fix

## 

# Linting

# Primary Linting

# TODO: Add the primary linting target here.

# Megalinter

.PHONY: megalinter
megalinter: 			## Run the Megalinter.
	docker run --platform linux/amd64 --rm \
    -v /var/run/docker.sock:/var/run/docker.sock:rw \
    -v $(shell pwd):/tmp/lint:rw \
    oxsecurity/megalinter:v9

## 
