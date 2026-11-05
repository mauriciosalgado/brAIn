# AWS RDS Snapshot Export to S3

Script to export an RDS snapshot to S3 and download it locally. Creates the required S3 bucket, KMS key, and IAM role, runs the export, downloads the data, then cleans everything up.

Links: [[aws-cli-sso-config]]
Tags: #aws #script #rds #s3

## Design Rationale

### Why create a KMS key?

AWS **requires** a KMS key for snapshot exports — even if the source snapshot is unencrypted. RDS encrypts all exported Parquet files with the key you provide.

### Why an IAM role with a trust policy for `export.rds.amazonaws.com`?

RDS needs to **assume** a role to write to your S3 bucket on your behalf. The trust policy allows the RDS export service to assume it. Without it, the export task fails with "unable to assume role".

## Prerequisites

- AWS CLI configured with SSO (see [[aws-cli-sso-config]])
- An existing RDS snapshot to export

## Variables

Edit and run this block first. It writes the variables to `/tmp/aws-rds-snapshot-export-to-s3.env` so all other blocks can source them.

```bash
cat > /tmp/aws-rds-snapshot-export-to-s3.env << 'EOF'
# execute-code runs with Obsidian's minimal PATH — add common tool dirs so CLIs are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export AWS_PROFILE="<aws-profile>"
export REGION="<aws-region>"
export BUCKET_NAME="<bucket-name>"
export KMS_ALIAS="alias/<kms-alias-name>"
export ROLE_NAME="<iam-role-name>"
export POLICY_NAME="<iam-policy-name>"
export SNAPSHOT_ARN="<snapshot-arn>"
export LOCAL_DOWNLOAD_DIR="<local-download-path>"
EOF

echo "Variables saved to /tmp/aws-rds-snapshot-export-to-s3.env"
```

## AWS Login

Before running the scripts you need to authenticate to AWS.

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

aws sso login --sso-session <sso-session>
```

## Create S3 Bucket

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

# --- Create KMS Key ---
KMS_KEY_ID=$(aws kms create-key \
  --region "$REGION" \
  --description "Encryption key for $BUCKET_NAME" \
  --query "KeyMetadata.KeyId" \
  --output text)
echo "KMS Key created: $KMS_KEY_ID"

aws kms create-alias \
  --region "$REGION" \
  --alias-name "$KMS_ALIAS" \
  --target-key-id "$KMS_KEY_ID"
echo "KMS Alias created: $KMS_ALIAS"

# --- Create S3 Bucket ---
aws s3api create-bucket \
  --region "$REGION" \
  --bucket "$BUCKET_NAME" \
  --create-bucket-configuration LocationConstraint="$REGION"
echo "Bucket created: $BUCKET_NAME"
```

## Create IAM Role

Creates an IAM role that the RDS service can assume to write snapshot exports to the bucket.

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

KMS_KEY_ID=$(aws kms describe-key \
  --region "$REGION" \
  --key-id "$KMS_ALIAS" \
  --query "KeyMetadata.KeyId" \
  --output text)

# --- Create trust policy (allows RDS export service to assume) ---
TRUST_POLICY=$(cat << POLICY
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "export.rds.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
POLICY
)

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --description "Role for RDS snapshot export to S3"
echo "IAM Role created: $ROLE_NAME"

# --- Create and attach write policy ---
WRITE_POLICY=$(cat << POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:GetObjectAcl",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:GenerateDataKeyWithoutPlaintext",
        "kms:ReEncryptFrom",
        "kms:ReEncryptTo",
        "kms:DescribeKey",
        "kms:CreateGrant",
        "kms:RetireGrant"
      ],
      "Resource": "arn:aws:kms:$REGION:$ACCOUNT_ID:key/$KMS_KEY_ID"
    }
  ]
}
POLICY
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document "$WRITE_POLICY"
echo "Write policy attached to role."

echo ""
echo "=== Summary ==="
echo "Bucket:   $BUCKET_NAME"
echo "KMS Key:  $KMS_KEY_ID"
echo "IAM Role: arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
```

## Export RDS Snapshot

Start the export task. This can take minutes to hours depending on snapshot size.

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

KMS_KEY_ID=$(aws kms describe-key \
  --region "$REGION" \
  --key-id "$KMS_ALIAS" \
  --query "KeyMetadata.KeyId" \
  --output text)

aws rds start-export-task \
  --region "$REGION" \
  --export-task-identifier "rds-export-$(date +%Y%m%d)" \
  --source-arn "$SNAPSHOT_ARN" \
  --s3-bucket-name "$BUCKET_NAME" \
  --iam-role-arn "arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME" \
  --kms-key-id "$KMS_KEY_ID"

echo "Export task started. Check status with:"
echo "aws rds describe-export-tasks --region $REGION"
```

## Check Export Status

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

aws rds describe-export-tasks \
  --region "$REGION" \
  --query "ExportTasks[?SourceArn=='$SNAPSHOT_ARN'].[ExportTaskIdentifier,Status,PercentProgress]" \
  --output table
```

## Download Locally

Once the export status is `COMPLETE`, download the exported files.

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

mkdir -p "$LOCAL_DOWNLOAD_DIR"

aws s3 cp "s3://$BUCKET_NAME/" "$LOCAL_DOWNLOAD_DIR/" \
  --recursive \
  --region "$REGION"

echo "Download complete: $LOCAL_DOWNLOAD_DIR"
du -sh "$LOCAL_DOWNLOAD_DIR"
```

## Cleanup

Delete the IAM role, S3 bucket (must be empty), and KMS key.

```bash
source /tmp/aws-rds-snapshot-export-to-s3.env

KMS_KEY_ID=$(aws kms describe-key \
  --region "$REGION" \
  --key-id "$KMS_ALIAS" \
  --query "KeyMetadata.KeyId" \
  --output text)

# --- Delete IAM role policy and role ---
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME"

aws iam delete-role --role-name "$ROLE_NAME"
echo "IAM Role deleted: $ROLE_NAME"

# --- Empty and delete S3 bucket ---
aws s3 rm "s3://$BUCKET_NAME" --recursive --region "$REGION"

aws s3api delete-bucket --region "$REGION" --bucket "$BUCKET_NAME"
echo "Bucket deleted: $BUCKET_NAME"

# --- Schedule KMS key deletion (minimum 7-day waiting period) ---
aws kms delete-alias \
  --region "$REGION" \
  --alias-name "$KMS_ALIAS"

aws kms schedule-key-deletion \
  --region "$REGION" \
  --key-id "$KMS_KEY_ID" \
  --pending-window-in-days 7
echo "KMS Key scheduled for deletion in 7 days: $KMS_KEY_ID"

# --- Remove the run's env file ---
rm -f /tmp/aws-rds-snapshot-export-to-s3.env

echo "Cleanup complete."
```

## References

- [AWS S3 Create Bucket CLI](https://docs.aws.amazon.com/cli/latest/reference/s3api/create-bucket.html)
- [AWS RDS Start Export Task](https://docs.aws.amazon.com/cli/latest/reference/rds/start-export-task.html)
- [Setting up access for RDS snapshot export to S3](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ExportSnapshot.html#USER_ExportSnapshot.SetupIAMRole)

