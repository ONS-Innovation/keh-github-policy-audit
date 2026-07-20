data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

# Get the ecs infrastructure outputs from the remote state data source
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "${var.env_name}-tf-state"
    key    = "${var.env_name}-ecs-infra/terraform.tfstate"
    region = "eu-west-2"
  }
}
