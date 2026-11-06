# Runbook: Rotate AWS Access Keys

Tags: #security #scripts

## Scope

We prefer no IAM users at all, but a handful of legacy integrations (a vendor SFTP bridge, an on-prem backup appliance) still use IAM user access keys. Keys must be rotated every 90 days; a Config rule flags anything older than 80 days. This runbook is not for database credentials or TLS certificates.

## Find Stale Keys

```bash
aws iam generate-credential-report --profile acme-prod
aws iam get-credential-report --query Content --output text --profile acme-prod \
  | base64 -d | awk -F, 'NR>1 && $9=="true" {print $1,$10}'
```

The tenth column lists last rotation date of access key 1.

## Rotate Without Downtime

An IAM user can hold two keys, which allows overlap.

```bash
aws iam create-access-key --user-name svc-sftp-bridge
# store new key in Secrets Manager, update the consumer, then:
aws iam update-access-key --user-name svc-sftp-bridge --access-key-id AKIAEXAMPLEOLD --status Inactive
# wait 7 days for errors, then
aws iam delete-access-key --user-name svc-sftp-bridge --access-key-id AKIAEXAMPLEOLD
```

Never delete the old key right away; set it Inactive first, and watch CloudTrail for `AccessDenied` events from that key ID.

## Confirm Last Use

`aws iam get-access-key-last-used --access-key-id AKIAEXAMPLEOLD` shows when the key last called the API. If it was used in the last hour by an unknown IP, treat it as compromised and use the leaked-key incident process.

## Prefer Roles

Whenever possible, replace the key with an IAM role: IRSA for pods, OIDC for GitHub Actions, instance profiles for EC2. Record removal of the last key as a quarterly goal.
