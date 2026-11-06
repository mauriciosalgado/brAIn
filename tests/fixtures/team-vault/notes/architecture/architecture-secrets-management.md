# Secrets Management Architecture

Tags: #security #architecture

## Where Secrets Live

Runtime secrets are stored in AWS Secrets Manager under the prefix `/<env>/<service>/`. The External Secrets Operator in each cluster syncs selected secrets into Kubernetes Secret objects every 10 minutes. Static configuration that is not secret stays in Helm values. Secrets never appear in Git in plaintext; infrastructure-level values that must be committed are encrypted with SOPS using a KMS key.

## Access Model

Each service has an IRSA role allowed `secretsmanager:GetSecretValue` only on its own prefix. Humans have no standing read access to production secrets; break-glass access is granted through the access review process for four hours and audited in CloudTrail. Secret values are encrypted with a per-environment KMS key, and the key policy denies use outside the account.

## Rotation Strategy

Database credentials are rotated by a Lambda on a 30-day schedule using the alternating-users pattern, so there is no downtime during a swap. API keys for third-party vendors are rotated manually each quarter and tracked in the access review spreadsheet. Pods pick up new values on restart, so services that cache credentials must reload on SIGHUP or be restarted by the rotation job.

## Detection

GitHub secret scanning with push protection is enabled org-wide, and we run gitleaks in CI as a second layer. Any hit is treated as a leak: rotate first, then investigate.
