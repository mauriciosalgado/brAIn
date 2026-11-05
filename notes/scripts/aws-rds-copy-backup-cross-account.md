# AWS RDS Copy Backup Cross-Account

Script to temporarily grant cross-account access and copy an RDS cluster snapshot from one account (e.g. Prod) to another (e.g. Dev). Handles KMS re-encryption and cleans up all temporary access after the copy.

Links: [[aws-cli-sso-config]]
Tags: #aws #script #rds

## Design Rationale

### Why KMS Grants instead of modifying the Key Policy?

KMS grants are **temporary and revocable**. Modifying a key policy is a permanent change that's easy to forget to revert and can accidentally broaden access. A grant is scoped to a specific principal and can be retired/revoked the moment the copy completes.

### Why copy to a manual snapshot first?

AWS Backup snapshots (prefixed `awsbackup:`) **cannot be shared via the RDS API** (`modify-db-cluster-snapshot-attribute` rejects them). They can be copied cross-account using AWS Backup's native `start-copy-job`, but that requires permanent vault policy changes in the destination. Copying to a manual snapshot first lets us use the RDS sharing path, which is fully temporary and revocable.

### Why re-encrypt in the destination account?

When you copy an encrypted snapshot cross-account, you **must** specify a KMS key owned by the destination account. This re-encrypts the data with the destination's key, removing any ongoing dependency on the source account's KMS key. Without this, the destination would permanently depend on the source key staying accessible.

### Why grant the destination account access to the source KMS key?

The destination account needs `kms:Decrypt` on the source KMS key to read the encrypted snapshot during the copy. Once the copy completes (re-encrypted with the destination's own key), this access is no longer needed — hence the cleanup.

### Why create a KMS key in the destination?

Cross-account snapshot copies require a **customer-managed KMS key** in the destination — the AWS managed `aws/rds` key can't be used for this. This key **cannot be deleted** during cleanup because the copied snapshot depends on it. It's scheduled for deletion only when you delete the destination snapshot.

### Why share/unshare the snapshot explicitly?

RDS snapshots are private by default. Sharing grants another account access to see and copy it. We revoke this after the copy so no permanent data-sharing path remains.

## Prerequisites

- AWS CLI configured with SSO (see [[aws-cli-sso-config]])
- The source snapshot ARN (from RDS or AWS Backup)

## Variables

Only provide the two account profiles, the snapshot ARN, its KMS key ARN, and a name for the copy. Everything else is derived or created by the script.

```bash
cat > /tmp/aws-rds-copy-backup-cross-account.env << 'EOF'
# execute-code runs with Obsidian's minimal PATH — add common tool dirs so CLIs are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export SRC_PROFILE="<source-aws-profile>"
export DST_PROFILE="<destination-aws-profile>"
export REGION="<aws-region>"
export SRC_SNAPSHOT_ARN="<source-snapshot-arn>"
export SRC_KMS_KEY_ARN="<source-kms-key-arn>"
export SNAPSHOT_NAME="<snapshot-copy-name>"
EOF

echo "Variables saved to /tmp/aws-rds-copy-backup-cross-account.env"
```

## AWS Login

Authenticate to both accounts before running the steps.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

aws sso login --sso-session <sso-session>
```

## Step 1 — Copy to Manual Snapshot (Source Account)

AWS Backup snapshots (prefixed `awsbackup:`) can't be shared via the RDS API. Copy to a manual snapshot first.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

MANUAL_SNAPSHOT_ARN=$(aws rds copy-db-cluster-snapshot \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --source-db-cluster-snapshot-identifier "$SRC_SNAPSHOT_ARN" \
  --target-db-cluster-snapshot-identifier "$SNAPSHOT_NAME" \
  --kms-key-id "$SRC_KMS_KEY_ARN" \
  --query "DBClusterSnapshot.DBClusterSnapshotArn" \
  --output text)

echo "Copying to manual snapshot. Waiting..."
aws rds wait db-cluster-snapshot-available \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME"
echo "Manual snapshot ready: $MANUAL_SNAPSHOT_ARN"
echo "export MANUAL_SNAPSHOT_ARN=\"$MANUAL_SNAPSHOT_ARN\"" >> /tmp/aws-rds-copy-backup-cross-account.env
```

## Step 2 — Grant KMS Access to Destination Account (Source Account)

Create a KMS grant so the destination account can decrypt the snapshot during copy.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

DST_ACCOUNT_ID=$(aws sts get-caller-identity \
  --profile "$DST_PROFILE" \
  --query "Account" --output text)

GRANT_ID=$(aws kms create-grant \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --key-id "$SRC_KMS_KEY_ARN" \
  --grantee-principal "arn:aws:iam::$DST_ACCOUNT_ID:root" \
  --operations Decrypt Encrypt GenerateDataKey GenerateDataKeyWithoutPlaintext ReEncryptFrom ReEncryptTo DescribeKey CreateGrant RetireGrant \
  --query "GrantId" \
  --output text)

echo "KMS Grant created: $GRANT_ID"
echo "export KMS_GRANT_ID=\"$GRANT_ID\"" >> /tmp/aws-rds-copy-backup-cross-account.env
echo "export DST_ACCOUNT_ID=\"$DST_ACCOUNT_ID\"" >> /tmp/aws-rds-copy-backup-cross-account.env
```

## Step 3 — Share Snapshot with Destination Account (Source Account)

Allow the destination account to see and copy the manual snapshot.

> [!NOTE]
> Every RDS snapshot has a `restore` attribute — a list of account IDs allowed to see and copy it. By default, only the owning account has access. This command adds the destination account to that list. Without it, the destination would get "snapshot not found" in Step 5. This grants visibility and copy permission only — the KMS grant from Step 2 is still needed to decrypt the data.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

aws rds modify-db-cluster-snapshot-attribute \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME" \
  --attribute-name restore \
  --values-to-add "$DST_ACCOUNT_ID"

echo "Snapshot shared with account: $DST_ACCOUNT_ID"
```

## Step 4 — Create KMS Key in Destination Account (Optional)

Cross-account snapshot copies require a customer-managed KMS key in the destination. If one already exists, skip this step and inject its ID into the env file instead:

```bash
echo 'export DST_KMS_KEY_ID="<existing-kms-key-id>"' >> /tmp/aws-rds-copy-backup-cross-account.env
```

Otherwise, create a new one:

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

DST_KMS_KEY_ID=$(aws kms create-key \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --description "KMS key for cross-account snapshot copy: $SNAPSHOT_NAME" \
  --query "KeyMetadata.KeyId" \
  --output text)

aws kms create-alias \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --alias-name "alias/$SNAPSHOT_NAME-kms" \
  --target-key-id "$DST_KMS_KEY_ID"

echo "Destination KMS Key created: $DST_KMS_KEY_ID"
echo "export DST_KMS_KEY_ID=\"$DST_KMS_KEY_ID\"" >> /tmp/aws-rds-copy-backup-cross-account.env
```

## Step 5 — Copy Snapshot to Destination Account (Destination Account)

Copy the shared snapshot into the destination account. This re-encrypts it with the destination's KMS key, removing any dependency on the source key.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

aws rds copy-db-cluster-snapshot \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --source-db-cluster-snapshot-identifier "$MANUAL_SNAPSHOT_ARN" \
  --target-db-cluster-snapshot-identifier "$SNAPSHOT_NAME" \
  --kms-key-id "$DST_KMS_KEY_ID"

echo "Copying snapshot to destination. Waiting..."
aws rds wait db-cluster-snapshot-available \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME"
echo "Snapshot available in destination: $SNAPSHOT_NAME"
```

## Cleanup Source

Revoke the KMS grant and delete the manual snapshot from the source account. The destination KMS key is **not deleted** — the copied snapshot depends on it. If the env was lost, run the "Recover Environment" step first.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

# --- Revoke KMS grant ---
aws kms revoke-grant \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --key-id "$SRC_KMS_KEY_ARN" \
  --grant-id "$KMS_GRANT_ID"
echo "KMS Grant revoked: $KMS_GRANT_ID"

# --- Delete manual snapshot ---
aws rds delete-db-cluster-snapshot \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME"
echo "Manual snapshot deleted: $SNAPSHOT_NAME"

echo "Source cleanup complete. Destination snapshot remains: $SNAPSHOT_NAME"
```

## Cleanup Destination (When No Longer Needed)

When the copied snapshot is no longer needed, delete it and its KMS key.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

# --- Delete destination snapshot ---
aws rds delete-db-cluster-snapshot \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME"
echo "Destination snapshot deleted: $SNAPSHOT_NAME"

# --- Delete destination KMS key ---
aws kms delete-alias \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --alias-name "alias/$SNAPSHOT_NAME-kms"
aws kms schedule-key-deletion \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --key-id "$DST_KMS_KEY_ID" \
  --pending-window-in-days 7
echo "KMS Key scheduled for deletion in 7 days: $DST_KMS_KEY_ID"

# --- Remove the run's env file (this is the final step of the whole runbook) ---
rm -f /tmp/aws-rds-copy-backup-cross-account.env

echo "Destination cleanup complete."
```

## Recover Environment (If Needed)

Re-derives all variables from AWS in case the env file was lost. Requires the Variables block to be run first.

```bash
source /tmp/aws-rds-copy-backup-cross-account.env

DST_ACCOUNT_ID=$(aws sts get-caller-identity \
  --profile "$DST_PROFILE" \
  --query "Account" --output text)

MANUAL_SNAPSHOT_ARN=$(aws rds describe-db-cluster-snapshots \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME" \
  --query "DBClusterSnapshots[0].DBClusterSnapshotArn" \
  --output text)

SRC_KMS_KEY_ARN=$(aws rds describe-db-cluster-snapshots \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --db-cluster-snapshot-identifier "$SNAPSHOT_NAME" \
  --query "DBClusterSnapshots[0].KmsKeyId" \
  --output text)

KMS_GRANT_ID=$(aws kms list-grants \
  --profile "$SRC_PROFILE" \
  --region "$REGION" \
  --key-id "$SRC_KMS_KEY_ARN" \
  --query "Grants[?GranteePrincipal=='arn:aws:iam::${DST_ACCOUNT_ID}:root'].GrantId | [0]" \
  --output text)

DST_KMS_KEY_ID=$(aws kms describe-key \
  --profile "$DST_PROFILE" \
  --region "$REGION" \
  --key-id "alias/$SNAPSHOT_NAME-kms" \
  --query "KeyMetadata.KeyId" \
  --output text)

cat >> /tmp/aws-rds-copy-backup-cross-account.env << EOF
export DST_ACCOUNT_ID="$DST_ACCOUNT_ID"
export MANUAL_SNAPSHOT_ARN="$MANUAL_SNAPSHOT_ARN"
export SRC_KMS_KEY_ARN="$SRC_KMS_KEY_ARN"
export KMS_GRANT_ID="$KMS_GRANT_ID"
export DST_KMS_KEY_ID="$DST_KMS_KEY_ID"
EOF

echo "Environment recovered to /tmp/aws-rds-copy-backup-cross-account.env"
```

## References

- [Sharing encrypted RDS snapshots cross-account](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/USER_ShareSnapshot.html)
- [KMS Grants](https://docs.aws.amazon.com/kms/latest/developerguide/grants.html)
- [copy-db-cluster-snapshot CLI](https://docs.aws.amazon.com/cli/latest/reference/rds/copy-db-cluster-snapshot.html)
