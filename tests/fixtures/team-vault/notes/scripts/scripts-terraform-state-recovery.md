# Runbook: Recover Terraform State

Tags: #terraform #scripts

## Stuck Lock

If a pipeline was cancelled mid-apply, the DynamoDB lock may remain. Verify no apply is running in GitHub Actions, then run `terraform force-unlock <LOCK_ID>` using the ID in the error message.

## Corrupted or Wrong State

State files are versioned in S3. List versions and restore the one before the bad apply:

```bash
aws s3api list-object-versions --bucket acme-prod-tfstate --prefix eks/terraform.tfstate --max-items 5
aws s3api get-object --bucket acme-prod-tfstate --key eks/terraform.tfstate --version-id <ID> restored.tfstate
terraform state push restored.tfstate
```

`state push` refuses if the serial is lower than the current one; pass `-force` only after a second engineer agrees.

## Resource Exists but Not in State

Use import: `terraform import module.rds.aws_db_instance.this orders-prod`. Then run plan and expect a clean or minimal diff. If you renamed a resource in code, use a `moved {}` block rather than destroy-and-create.

## Removing Without Destroying

`terraform state rm aws_s3_bucket.legacy` forgets the resource without deleting it. Do this before removing code for resources that must stay alive.
