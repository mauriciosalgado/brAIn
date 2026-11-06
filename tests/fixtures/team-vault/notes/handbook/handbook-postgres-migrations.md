# PostgreSQL Migration Rules

Tags: #postgresql #handbook

## Tooling

Schema changes use Flyway with versioned SQL files in each service's `db/migration` directory, named `V<yyyymmddHHMM>__description.sql`. Migrations run as a Helm pre-upgrade hook Job, never from application startup. Each migration must be reviewed by someone from the data platform group.

## Safe Patterns

Add columns as nullable or with a constant default (fast in Postgres 11+). Create indexes with `CREATE INDEX CONCURRENTLY`, outside a transaction (`-- flyway:executeInTransaction=false`). Add foreign keys as `NOT VALID` then `VALIDATE CONSTRAINT` in a later migration. Set `lock_timeout = '3s'` at the top so a blocked ALTER fails fast instead of queuing behind a long query and stalling all traffic.

## Forbidden Without Approval

Dropping columns or tables (deprecate first, drop one release later), `ALTER COLUMN TYPE` on tables over 1 GB, `VACUUM FULL`, and any lock-taking statement on the `orders` table during business hours.

## Table Partitioning

Tables expected to exceed 200 GB use native declarative partitioning by month on `created_at`. The `pg_partman` extension creates future partitions 3 months ahead. Queries must include the partition key or they scan every partition.

## Pre-Migration Safety

Before a risky migration, take a manual RDS snapshot and record its identifier in the PR. Test timing against a restored copy of production, not a tiny dev database.
