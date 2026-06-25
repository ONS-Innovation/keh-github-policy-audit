# KEH Template Repository

This repository is a template for all new Knowledge Exchange Hub (KEH) repositories. It contains the basic structure and files that are common to all KEH repositories, such as CODEOWNERS, sample GitHub Actions workflows, and a README template.

## Usage

### Creating a New Repository

To use this template when creating a new repository, simply select "Use this template" on GitHub and follow the prompts to create your new repository based on this template. This will ensure that your new repository has the necessary structure and files to maintain consistency across all KEH repositories.

### Further Setup

Since this repository is intended for all KEH repositories, it needs some additional setup once you have created your new repository. The steps below outline the necessary customisation and setup:

1. **Update the README**: Replace the content of the README with information relevant to your project. This should use the template below as a starting point.
2. **Update CODEOWNERS**: Modify the CODEOWNERS file to chose the appropriate team. The 2 options for KEH are within the file itself.
3. **Set up GitHub Actions**: This repository has already setup some sample GitHub Actions workflows (i.e. MkDocs related actions and Megalinter). In addition to this, the repository should also have its primary language linter and test workflow set up. Placeholders for these workflows are already in place, so you just need to fill in the details ([ci-fmt](./.github/workflows/ci-fmt.yml), [ci-test](./.github/workflows/ci-test.yml)). The actions use paths to only run when files in certain directories are changed (e.g. `src` and `tests`), so make sure to update these paths if your repository has a different structure.
4. **Setup Repository Settings**: The repository should have the following settings configured:
   1. **Contributors**:
      1. Add `keh-dev` to the repository with **Write** access.
      2. Add `keh-dev-admin` to the repository with **Admin** access.
   2. **Branch Protection Rules**:
      1. Within `Rules > Rulesets`, create a new _branch ruleset_ for the `main` branch.
      2. Add the following rules to the ruleset:
         1. Add `keh-dev-admin` to the Bypass List. This is for emergency situations where you need to bypass branch protection rules.
         2. Target the Default Branch (`main`).
         3. Restrict deletions.
         4. Require a pull request before merging. This should require **at least 2 approving reviews**.
         5. Block force pushes.
      3. Save the ruleset.
5. **Setup Repository for Project Use**: Now that the housekeeping is done, you can set up the repository for project use.

#### Python Specific Setup

When using Python, Poetry has already been setup for dependency management since it is used for documentation.

Ensure that you update the `pyproject.toml` file to match the needs of your project.

## README Template

The below is a template for the README file that should be used for all KEH repositories. This template provides a basic structure and can be customised to fit the specific needs of your project.

Everything above this line should be removed when customising the README for your project.

---

# Project Name <!-- markdownlint-disable-line MD025 -->

<!-- A brief description of the project goes here. -->

## Table of Contents

<!-- A table of contents for the README goes here. -->
<!-- This can be automatically generated using a tool like the Markdown All in One extension for Visual Studio Code. -->

## Prerequisites

<!-- A list of prerequisites for the project goes here. -->

## Makefile

This project uses a Makefile to simplify common tasks.
To see the available commands, run:

```bash
make help
```

## Running the Project

<!-- Instructions for running the project go here. This can include commands to start the project, as well as any necessary configuration steps. -->

## Deployment

### Deployments with Concourse

<!-- Instructions for deploying the project using Concourse go here. This can be copied from other KEH repositories. -->

### Manual Deployment

<!-- Instructions for manually deploying the project go here. This can be copied from other KEH repositories. -->

## Documentation

<!-- Add any additional information if needed -->

This repository uses [MkDocs](https://www.mkdocs.org/) for documentation. The documentation source files are located in the `docs` directory.

### GitHub Actions for Documentation

MkDocs gets deployed to GitHub Pages using GitHub Actions. The workflow for this is located at `.github/workflows/deploy-docs.yml`.
Before deployment, another GitHub Action workflow runs to check that the documentation builds correctly and has no linting or formatting issues.
This workflow is located at `.github/workflows/ci-docs.yml`.

### Local Development of Documentation

To run the documentation locally:

1. Create a Python virtual environment and activate it.

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install the dependencies for MkDocs.

   ```bash
   make docs-install
   ```

3. Run the MkDocs development server.

   ```bash
   make docs-serve
   ```

## Linting and Testing

### GitHub Actions

This repository has GitHub Actions workflows set up for linting and testing. The workflows are located at:

- `.github/workflows/ci-fmt.yml` for linting and formatting checks (primary language).
- `.github/workflows/ci-test.yml` for running automated tests.
- `.github/workflows/ci-docs.yml` for checking that the documentation builds correctly and has no linting or formatting issues.
- `.github/workflows/megalinter.yml` for running MegaLinter, which checks for linting and formatting issues across multiple languages and file types (this is a catch-all linter).
- `.github/workflows/deploy-docs.yml` for deploying documentation to GitHub Pages.

### Running Tests and Linters Locally

#### Primary Language

<!-- Instructions for running the primary language linter and tests locally go here. This will depend on the primary language of the project. -->

#### MegaLinter

This repository uses MegaLinter for comprehensive linting across multiple languages and file types.
We use this so that all additional assets in the repository (e.g. YAML files, Markdown files, etc.) are also linted and checked for formatting issues, without having to set up specific linters for each file type.

To run MegaLinter locally, you can use the following command:

```bash
make megalinter
```

#### Documentation linting and building

This repository uses Markdownlint for linting the documentation. To run Markdownlint locally, you can use the following:

```bash
make docs-lint
```

**Note:** This will install `markdownlint-cli` globally via npm if it is not already installed.

To apply automatic fixes for any linting issues found by Markdownlint, you can use:

```bash
make docs-fix
```

To test that the documentation builds correctly, you can use the following command:

```bash
make docs-build
```

**Note:** This depends on MkDocs being set up for the repository. Instructions for setting up MkDocs can be found in the [Documentation](#documentation) section of this README.
