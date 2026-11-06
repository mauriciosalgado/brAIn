# Runbook: KMS Key Rotation and Recovery

Tags: #security #scripts

## Automatic Rotation

Customer-managed symmetric keys have rotation enabled with a 365-day period: `aws kms enable-key-rotation --key-id alias/prod-data`. Rotation creates new key material while retaining old material to decrypt existing data, so nothing is re-encrypted and no application change is needed. The key ID and ARN stay the same.

## Check Status

```bash
aws kms get-key-rotation-status --key-id alias/prod-data
aws kms list-key-rotations --key-id alias/prod-data
```

## Deleted Keys

Key deletion has a pending window of 30 days for our keys (minimum is 7). A key in `PendingDeletion` state can be rescued with `aws kms cancel-key-deletion`, followed by `enable-key` because cancelled keys stay disabled. After the window expires the data encrypted by that key is lost permanently, which is why Terraform marks keys with `prevent_destroy`.

## Access Denied Troubleshooting

If a service gets `AccessDeniedException` on decrypt, check both the key policy and the IAM policy; both must allow it unless the key policy delegates to IAM. For S3 and RDS snapshots shared cross-account, the destination account must be named in the key policy.
