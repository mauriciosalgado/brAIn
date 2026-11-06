# ADR-0007: SOPS With KMS for Committed Secrets

Tags: #security #decision

## Context

A few values must live in Git next to infrastructure code: bootstrap tokens, Terraform provider credentials, and Helm values for operators that start before the External Secrets Operator exists.

## Decision

Encrypt those files with SOPS using AWS KMS keys, one per environment. Only the values are encrypted, so diffs stay readable. The `.sops.yaml` file defines creation rules by path.

## Constraints

Decrypting requires `kms:Decrypt` on the key, granted to CI roles and the platform admin permission set. We rejected age keys because distributing and rotating private keys by hand brings us back to the leak risk we want to avoid. Anything runtime-facing goes to Secrets Manager instead; SOPS is for bootstrap only.
