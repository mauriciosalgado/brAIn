# ADR-0006: RDS Over Self-Hosted PostgreSQL

Tags: #postgresql #decision

## Context

Until 2023 the `accounts` database ran on EC2 with pgBackRest and Patroni. A failover test showed a 4-minute recovery and the team spent roughly 15% of its time on database care.

## Decision

Move primary application databases to RDS for PostgreSQL Multi-AZ. Self-hosted Postgres remains only for the analytics warehouse, where we need extensions and a filesystem layout RDS cannot provide (for example custom `pg_cron` schedules and large `work_mem`).

## Reasoning

RDS Multi-AZ fails over in 60-120 seconds, handles minor version patching and backups, and integrates with IAM and KMS. Premium is about 30% over equivalent EC2 plus EBS, which we judged cheaper than engineer time.

## Consequences

We lose superuser access and some extensions; we gain `rds_superuser` and a managed parameter group. Backup procedures differ between the two worlds, so there are two separate runbooks.
