# Terraform Conventions

Tags: #terraform #handbook

## Repository Layout

The `infra` repo is split into `modules/` (reusable) and `live/<account>/<region>/<stack>/` (instantiations). Each stack has its own state file, kept small so plans run under two minutes. We never run `terraform apply` from a laptop against staging or prod; applies run in the pipeline after plan approval.

## State and Locking

State is stored in an S3 bucket per account with versioning and SSE-KMS, and locking uses a DynamoDB table named `tf-locks`. If a lock is stuck after a crashed run, confirm nobody else is applying and use `terraform force-unlock <ID>`. Do not delete the DynamoDB item by hand.

## Module Rules

Modules pin provider versions with `~>` constraints and expose only variables that callers need. Every resource that supports tags receives the standard tag map via `default_tags`. Use `for_each` with stable keys rather than `count` to avoid index shifts that cause surprise destroys.

## Plan Review

Reviewers read the plan, not just the diff. Treat any line with `must be replaced` or `destroy` as requiring a comment explaining it. RDS, KMS keys and S3 buckets carry `lifecycle { prevent_destroy = true }`.

## Versions

We pin Terraform at 1.7.x with `.terraform-version` and tfenv. Provider upgrades happen in a dedicated PR, applied first in dev.
