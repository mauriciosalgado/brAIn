# 2025-06-17 Leaked AWS Access Key in Public Repository

Tags: #incident #security

## Summary

On 17 June 2025 GitHub secret scanning notified us that an IAM user access key for the `svc-sftp-bridge` user was committed in a public fork of an example repository. The key was active for 6 days. CloudTrail showed no use from unknown addresses, but 14 `ListBuckets` calls came from an IP in an unexpected network before it was disabled.

## Response

1. Set the key Inactive within 8 minutes of the alert (`aws iam update-access-key --status Inactive`).
2. Reviewed CloudTrail Lake for the key ID over the prior 14 days.
3. Attached an explicit deny policy to the user while investigating.
4. Created a replacement key and updated the integration.

## Impact

The permission set on the user allowed only `s3:GetObject` and `s3:ListBucket` on one bucket, so no data left the account as far as logs prove. Still, the bucket object listing exposed filenames.

## Root Cause

A contractor copied a configuration sample containing the key into a personal fork. Push protection was not enabled on that user's fork.

## Actions

Org-wide push protection and gitleaks in CI. Rotation of all legacy keys to 90-day schedule. Plan to replace the SFTP bridge with a role-based flow.
