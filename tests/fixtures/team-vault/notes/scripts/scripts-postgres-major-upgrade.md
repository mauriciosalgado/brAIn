# Runbook: Major Version Upgrade of Postgres on RDS

Tags: #postgresql #scripts

## Overview

We upgrade RDS Postgres major versions roughly every two years (14 to 15 is the most recent). RDS supports in-place upgrades via `pg_upgrade` under the hood, which for a 1 TB database takes 20-40 minutes of downtime, or a blue/green deployment that limits the switchover to about a minute. We use blue/green for Tier 1 databases.

### Decision Table

| Database size | Tolerable downtime | Method |
|---|---|---|
| < 100 GB | 15 min | in-place |
| 100 GB - 2 TB | 15 min | in-place with rehearsal |
| any | < 2 min | blue/green |
| uses logical replication slots | any | blue/green or dump/restore (see below) |

## Preparation

Review the release notes for removed features: Postgres 15 changed the default permissions of the `public` schema, which broke two services that created tables as non-owners. Check extensions with `select extname, extversion from pg_extension;` and compare with the supported list for the target version. Replication slots block in-place upgrades: drop or recreate them afterward.

### Rehearse on a Copy

Restore the latest snapshot to a new instance and upgrade it. Record the duration, the number of rows in `pg_stat_user_tables`, and run `ANALYZE` because statistics are not preserved. Also run the application's integration suite against the copy.

## Blue/Green Procedure

```bash
aws rds create-blue-green-deployment \
  --blue-green-deployment-name orders-15 \
  --source arn:aws:rds:us-east-1:111111111111:db:orders-prod \
  --target-engine-version 15.5 \
  --target-db-parameter-group-name orders-pg15
aws rds describe-blue-green-deployments --query 'BlueGreenDeployments[0].Status'
```

Wait until replication is caught up (lag near zero), confirm that read-only validation queries behave as expected on the green side, then:

```bash
aws rds switchover-blue-green-deployment --blue-green-deployment-identifier bgd-abc123 --switchover-timeout 300
```

Writes are blocked for roughly 45-60 seconds during the switchover. DNS endpoints stay the same, but clients that cached IPs or have long-lived TCP connections must reconnect, so restart PgBouncer right after.

## After the Upgrade

Run `ANALYZE` on the largest tables; planners can choose bad plans until statistics are rebuilt. Keep the old blue instance for 7 days as a rollback source, then delete. Rolling back after writes have landed on green means losing those writes, so decide within the first hour.

### Cleaning Up

Delete the blue/green deployment object (this does not delete instances), then delete the old instance with a final snapshot named `orders-prod-pre15-final`. Update the Terraform state with `terraform import` for the new instance name or alias.

## Logical Replication Slots

If the database feeds a CDC pipeline through a logical replication slot, the slot is not carried over by an in-place upgrade. Pause the connector, upgrade, recreate the slot, and let the connector take a new snapshot. This creates duplicates downstream, which consumers must dedupe by event ID.

## Timeline Template

T-14 days: announce. T-7: rehearsal. T-1: freeze migrations. T0: pre-snapshot, switch, validate, announce. T+7: delete the old instance.
