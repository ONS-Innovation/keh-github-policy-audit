locals {
  lambda_source_root      = "${path.module}/../build/lambdas"
  lambda_name_prefix      = "${var.env_name}-github-policy-audit"
  audit_output_bucket     = "${var.env_name}-github-policy-audit"
  scorecard_config_s3_key = "config/scorecard_criteria.json"
  dependency_layer_s3_key = "layers/dependency-layer.zip"

  lambda_definitions = {
    list_repositories = {
      zip_path = "${local.lambda_source_root}/list_repositories.zip"
      handler  = "functions.list_repositories.handler.handler"
      timeout  = 600
    }
    list_teams = {
      zip_path = "${local.lambda_source_root}/list_teams.zip"
      handler  = "functions.list_teams.handler.handler"
    }
    rate_limit = {
      zip_path = "${local.lambda_source_root}/rate_limit.zip"
      handler  = "functions.rate_limit.handler.handler"
    }
    dependabot_slo = {
      zip_path = "${local.lambda_source_root}/organisation_checks-dependabot_slo.zip"
      handler  = "functions.organisation_checks.dependabot_slo.handler.handler"
      timeout  = 300
    }
    secret_scanning_slo = {
      zip_path = "${local.lambda_source_root}/organisation_checks-secret_scanning_slo.zip"
      handler  = "functions.organisation_checks.secret_scanning_slo.handler.handler"
      timeout  = 300
    }
    team_maintainer = {
      zip_path = "${local.lambda_source_root}/organisation_checks-team_maintainer.zip"
      handler  = "functions.organisation_checks.team_maintainer.handler.handler"
    }
    codeowners = {
      zip_path = "${local.lambda_source_root}/repository_checks-codeowners.zip"
      handler  = "functions.repository_checks.codeowners.handler.handler"
    }
    dependabot = {
      zip_path = "${local.lambda_source_root}/repository_checks-dependabot.zip"
      handler  = "functions.repository_checks.dependabot.handler.handler"
    }
    external_pull_request = {
      zip_path = "${local.lambda_source_root}/repository_checks-external_pull_request.zip"
      handler  = "functions.repository_checks.external_pull_request.handler.handler"
    }
    gitignore = {
      zip_path = "${local.lambda_source_root}/repository_checks-gitignore.zip"
      handler  = "functions.repository_checks.gitignore.handler.handler"
    }
    inactivity = {
      zip_path = "${local.lambda_source_root}/repository_checks-inactivity.zip"
      handler  = "functions.repository_checks.inactivity.handler.handler"
    }
    license = {
      zip_path = "${local.lambda_source_root}/repository_checks-license.zip"
      handler  = "functions.repository_checks.license.handler.handler"
    }
    naming_convention = {
      zip_path = "${local.lambda_source_root}/repository_checks-naming_convention.zip"
      handler  = "functions.repository_checks.naming_convention.handler.handler"
    }
    pirr = {
      zip_path = "${local.lambda_source_root}/repository_checks-pirr.zip"
      handler  = "functions.repository_checks.pirr.handler.handler"
    }
    readme = {
      zip_path = "${local.lambda_source_root}/repository_checks-readme.zip"
      handler  = "functions.repository_checks.readme.handler.handler"
    }
    repository_access = {
      zip_path = "${local.lambda_source_root}/repository_checks-repository_access.zip"
      handler  = "functions.repository_checks.repository_access.handler.handler"
    }
    security_scanning = {
      zip_path = "${local.lambda_source_root}/repository_checks-security_scanning.zip"
      handler  = "functions.repository_checks.security_scanning.handler.handler"
    }
    store_repository_output = {
      zip_path = "${local.lambda_source_root}/store_repository_output.zip"
      handler  = "functions.store_repository_output.handler.handler"
    }
    store_output = {
      zip_path = "${local.lambda_source_root}/store_output.zip"
      handler  = "functions.store_output.handler.handler"
    }
  }

  repository_check_names = [
    "codeowners",
    "dependabot",
    "external_pull_request",
    "gitignore",
    "inactivity",
    "license",
    "naming_convention",
    "pirr",
    "readme",
    "repository_access",
    "security_scanning",
  ]
}
