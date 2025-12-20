terraform {
  backend "s3" {
    bucket       = "devpitio-terraform-state-654654346276"
    key          = "route53-failover/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
    # Profile can be set via AWS_PROFILE env var or -backend-config="profile=name"
  }
}
