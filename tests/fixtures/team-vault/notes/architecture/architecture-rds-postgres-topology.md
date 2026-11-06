# RDS PostgreSQL Topology

Tags: #postgresql #architecture

## Instances and Sizing

Primary application databases run on Amazon RDS for PostgreSQL 15. The `orders` database is a db.r6g.2xlarge Multi-AZ instance with 1 TB gp3 storage provisioned at 6000 IOPS; `accounts` is a db.r6g.xlarge Multi-AZ with 500 GB. Storage autoscaling is enabled with a ceiling of 2 TB. Parameter groups are managed in Terraform; `max_connections` is derived from instance memory, and applications must go through PgBouncer rather than connect directly.

## Replicas

Each production database has one in-region read replica used by reporting and the search indexer, plus a cross-region replica in us-west-2 that exists only for disaster recovery. Replica lag is graphed in Grafana; we page when read-replica lag exceeds 60 seconds for five minutes. Applications must never assume reads from the replica are fresh, so anything involving a just-written row reads from the primary.

## Connection Pooling

PgBouncer runs as a Deployment of 3 pods in each application namespace in transaction pooling mode, `default_pool_size=20` and `max_client_conn=2000`. Because transaction mode breaks session-level features, prepared statements must use protocol-level binding and advisory locks must be transaction-scoped. The RDS Proxy option was evaluated and rejected on cost.

## Maintenance and Backups

Maintenance window is Sunday 04:00-05:00 UTC. Automated backups retain 14 days with point-in-time recovery; manual snapshots are taken before any migration marked risky. Encryption at rest uses a customer-managed KMS key per environment, which means snapshots shared across accounts require granting the destination account access to that key.
