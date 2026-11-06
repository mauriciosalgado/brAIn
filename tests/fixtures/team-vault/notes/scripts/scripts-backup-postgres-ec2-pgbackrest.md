# Runbook: Back Up Self-Hosted Postgres on EC2 With pgBackRest

Tags: #backup #scripts

## Scope

The analytics warehouse (`wh-pg-01`, Postgres 14 on an r6i.4xlarge EC2 with 4 TB gp3) is not on RDS, so none of RDS's snapshot features apply. We back it up with pgBackRest to the S3 bucket `acme-prod-pgbackrest` with SSE-KMS. WAL is archived continuously, so recovery point objective is about 1 minute.

## Backup Schedule

A weekly full backup runs Sunday 01:00 UTC, differential backups every other night, and WAL is pushed by `archive_command`. Retention is `repo1-retention-full=4` and `repo1-retention-diff=14`.

```bash
sudo -u postgres pgbackrest --stanza=warehouse --type=full backup
sudo -u postgres pgbackrest --stanza=warehouse info
```

A full backup of 2.8 TB takes about 90 minutes using `process-max=6` and zstd compression level 3, resulting in roughly 900 GB in S3.

## Checking WAL Archiving

If `archive_command` fails, WAL piles up in `pg_wal` and the disk can fill, which stops the database. Check with:

```bash
psql -c "select archived_count, failed_count, last_failed_time from pg_stat_archiver;"
```

Alert `PgArchiveFailing` fires when `failed_count` increases for 10 minutes.

## Restore Procedure

1. Stop Postgres on the target host and empty the data directory.
2. Restore to a point in time:

```bash
sudo -u postgres pgbackrest --stanza=warehouse --delta \
  --type=time --target="2025-06-02 14:30:00+00" --target-action=promote restore
```

3. Start Postgres and wait for recovery to finish; watch `postgresql.log` for "database system is ready to accept connections".
4. Run `pgbackrest check` to confirm archiving works again before reconnecting clients.

A restore of the full dataset has measured 2h 40m.

## Verification

Monthly, a Jenkins-free scheduled job restores the latest backup to a scratch instance and runs `pg_amcheck`. A failed verification pages the data platform owner during business hours.
