variable "env_name" {
  description = "AWS environment"
  type        = string
  default     = "sdp-dev"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "project_tag" {
  description = "Project"
  type        = string
  default     = "SDP"
}

variable "team_owner_tag" {
  description = "Team Owner"
  type        = string
  default     = "Knowledge Exchange Hub"
}

variable "business_owner_tag" {
  description = "Business Owner"
  type        = string
  default     = "DST"
}

variable "github_owner" {
  description = "GitHub organisation owner passed to the state machine input."
  type        = string
}

variable "github_app_id_secret_name" {
  description = "Secrets Manager secret name containing GitHub App ID JSON payload."
  type        = string
}

variable "github_private_key_secret_name" {
  description = "Secrets Manager secret name containing GitHub App private key."
  type        = string
}

variable "lambda_runtime" {
  description = "Lambda runtime for all functions."
  type        = string
  default     = "python3.12"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds for all functions."
  type        = number
  default     = 120
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB for all functions."
  type        = number
  default     = 512
}

variable "lambda_reserved_concurrent_executions" {
  description = "Reserved concurrent executions per Lambda function. Set to -1 for unreserved (not recommended)."
  type        = number
  default     = 10
}

variable "github_client_cache_ttl_seconds" {
  description = "TTL in seconds for in-process GitHub client reuse within warm Lambda runtimes."
  type        = number
  default     = 300
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log group retention period in days for Lambda functions."
  type        = number
  default     = 90
}

variable "step_function_log_retention_days" {
  description = "CloudWatch log group retention period in days for the Step Functions state machine."
  type        = number
  default     = 90
}

variable "repository_map_max_concurrency" {
  description = "MaxConcurrency for repository checks map state."
  type        = number
  default     = 5
}

variable "team_map_max_concurrency" {
  description = "MaxConcurrency for team maintainer map state."
  type        = number
  default     = 5
}

variable "dependabot_slo_levels" {
  description = "Severity levels passed to dependabot_slo check. Defaults to all severities."
  type        = list(string)
  default     = ["critical", "high", "medium", "low"]
}

variable "audit_schedule_expression" {
  description = "EventBridge cron expression for weekly execution."
  type        = string
  default     = "cron(0 8 ? * MON *)"
}

variable "audit_run_retention_days" {
  description = "Days to retain per-repository run artifacts under audit-runs/."
  type        = number
  default     = 30
}

variable "audit_summary_retention_days" {
  description = "Days to retain aggregated audit summaries under audit-results/."
  type        = number
  default     = 365
}
