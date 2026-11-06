# Runbook: Back Up and Restore an RDS Instance

Tags: #backup #scripts

## When to Use This

Use this for the managed RDS PostgreSQL databases (`orders`, `accounts`). RDS takes automated daily snapshots in the 02:00-03:00 UTC window and keeps them 14 days. This runbook covers manual snapshots before risky changes, point-in-time restore, and cross-account copy. It does not apply to Postgres on EC2 (see the pgBackRest runbook) or Kafka.

## Take a Manual Snapshot

```bash
aws rds create-db-snapshot \
  --db-instance-identifier orders-prod \
  --db-snapshot-identifier orders-prod-premigration-$(date +%Y%m%d%H%M) \
  --profile acme-prod
aws rds wait db-snapshot-available --db-snapshot-identifier <id> --profile acme-prod
```

A snapshot of a 1 TB instance normally completes in 10-20 minutes since only changed blocks are copied; I/O is briefly suspended on single-AZ only, not Multi-AZ. Manual snapshots never expire, so tag them with `expires=YYYY-MM-DD` and delete them after.

## Point-in-Time Restore

PITR creates a new instance; it never overwrites the original. The latest restorable time is typically within 5 minutes of now.

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier orders-prod \
  --target-db-instance-identifier orders-prod-restore \
  --restore-time 2025-03-12T09:41:00Z \
  --db-subnet-group-name prod-data --no-multi-az
```

The restored instance gets default parameter group and security group unless you pass them explicitly, a step people forget. Expect 25-40 minutes for 1 TB, longer if the first reads are lazily loaded from S3.

## Cross-Account and Cross-Region Copy

Snapshots are encrypted with a customer-managed KMS key, so before sharing with another account, add that account to the key policy and then run `aws rds modify-db-snapshot-attribute --attribute-name restore --values-to-add <account>`. The recipient must copy the snapshot, re-encrypting with their own key, before restoring.

## Verification

After a restore, connect through a bastion and run `SELECT count(*) FROM orders WHERE created_at > now() - interval '1 hour';` against both instances and compare. Our quarterly restore test requires a documented restore time and that the row count mismatch be under 0.1%.

## References

- RDS topology note for instance names and the KMS key layout.
