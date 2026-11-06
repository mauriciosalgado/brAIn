# Multi-Account AWS Structure

Tags: #aws #architecture

## Accounts

We use AWS Organizations with five accounts under a `workloads` OU and two under `security`: `acme-dev`, `acme-stg`, `acme-prod`, `acme-shared` (CI, VPN, Thanos), `acme-data` (data lake), plus `acme-logarchive` and `acme-audit`. Billing consolidates in the management account, which hosts nothing but Organizations and IAM Identity Center.

## Why Separate Accounts

Accounts are the strongest blast-radius boundary AWS offers. A compromised dev credential cannot touch production data, quotas are per account so a runaway dev load test cannot throttle prod API calls, and cost allocation becomes trivial.

## Account Vending

New accounts are created through Terraform and an Account Factory pipeline that applies the baseline: CloudTrail to the log archive, AWS Config recorder, GuardDuty, default EBS encryption, S3 account-level block public access, and an SSO permission set assignment. A new account normally takes 40 minutes end to end.

## Cross-Account Access

Access between accounts uses role assumption with an ExternalId for third parties and `aws:PrincipalOrgID` conditions for internal resources. Resource policies on KMS keys and S3 buckets name accounts explicitly.
