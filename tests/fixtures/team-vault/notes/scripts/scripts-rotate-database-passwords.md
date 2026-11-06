# Runbook: Rotate Database Passwords

Tags: #security #scripts

## Scope

This covers application database users on RDS PostgreSQL stored in Secrets Manager under `/prod/<service>/db`. The automated rotation runs every 30 days; this runbook is for emergency or manual rotation, for example after an employee with access leaves.

## The Alternating-Users Pattern

Each service has two Postgres roles, `orders_app_a` and `orders_app_b`, both with identical grants. The secret holds the credentials of the currently active role. Rotation changes the password of the inactive role, flips the secret to it, and later the other role is updated on the next cycle. This avoids a window where connections using the old password break.

## Manual Rotation Steps

```bash
aws secretsmanager rotate-secret --secret-id /prod/orders/db --profile acme-prod
aws secretsmanager describe-secret --secret-id /prod/orders/db \
  --query '{last:LastRotatedDate,stages:VersionIdsToStages}'
```

After rotation, the External Secrets Operator picks up the new value within 10 minutes. Force it with `kubectl annotate externalsecret orders-db force-sync=$(date +%s) --overwrite`, then restart the pods: `kubectl rollout restart deploy/orders-api`.

## PgBouncer Caveat

PgBouncer holds the credentials in its `userlist.txt` generated at start. Restart the PgBouncer deployment before application pods, otherwise connection attempts fail with `password authentication failed`.

## Verification

```bash
psql "host=orders-prod.example-corp.io user=orders_app_b dbname=orders" -c "select 1"
```

Then confirm in the `pg_stat_activity` view that no sessions remain under the previous role, and revoke old sessions with `pg_terminate_backend` if they do.
