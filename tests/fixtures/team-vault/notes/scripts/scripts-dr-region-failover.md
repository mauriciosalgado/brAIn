# Runbook: Regional Disaster Recovery Failover

Tags: #backup #scripts

## Objectives and Assumptions

The disaster recovery plan targets a recovery time objective of 4 hours and a recovery point objective of 15 minutes for Tier 1 services (orders, accounts, payments). The secondary region is us-west-2. DR is a pilot-light setup: databases and S3 replicate continuously, but Kubernetes capacity is only scaled to a minimum, and Kafka is not replicated apart from the archived critical topics.

### Declaring a Disaster

Only the incident commander with VP engineering approval can declare a regional failover. Typical triggers are an AWS regional outage lasting more than 60 minutes with no ETA, or loss of the primary region's control plane access. A partial outage in one zone is not a reason to fail over.

## Pre-Positioned Components

The us-west-2 VPC (10.50.0.0/16), an EKS cluster `plat-dr` with 3 system nodes, ECR replicated images, Secrets Manager replicas, Route 53 health checks and a cross-region RDS replica for each database exist at all times. Terraform for DR lives in `live/acme-prod/us-west-2/`.

## Step 1: Freeze and Assess

Post the declaration in `#inc-` channel, stop deploys, and confirm primary-region state. Check replica lag of the DR replicas: `aws rds describe-db-instances --region us-west-2 --query 'DBInstances[].[DBInstanceIdentifier,StatusInfos]'`. Record the last replicated transaction time; this defines data loss.

## Step 2: Promote Databases

```bash
aws rds promote-read-replica --db-instance-identifier orders-prod-dr --region us-west-2
aws rds wait db-instance-available --db-instance-identifier orders-prod-dr --region us-west-2
```

Promotion takes 5-10 minutes and is irreversible: the old primary can never become a replica again without rebuilding. Update the database endpoint in Secrets Manager's replica secret.

## Step 3: Scale Up Compute

Raise node group capacity to production levels using the DR Terraform stack with `-var dr_active=true`. General nodes need about 15 minutes. Then sync Argo CD applications for `plat-dr`; sync order is data services, then platform (ingress, external secrets), then applications by tier.

### Kafka Handling

Kafka is not available in the DR region. Bring up the 3-broker emergency cluster from the AMI, restore Tier 1 topics via replay from the S3 archive, and accept that anything beyond the archive window (roughly 10 minutes) is lost. Consumers use new group IDs suffixed `-dr`.

## Step 4: Shift Traffic

Lower DNS TTL beforehand (already 60 seconds for failover records), then update the Route 53 weighted records to send 100% to the us-west-2 load balancer. Verify with `dig api.prod.example-corp.io` and run the smoke suite against the DR endpoint. Expect clients with cached resolution to take up to 5 minutes to move.

## Step 5: Failback

Failback is a planned project, not an emergency step. Rebuild the primary region replicas from the DR primary, let them catch up, schedule a maintenance window and reverse the DNS change. Do not attempt failback within 48 hours of the original region's recovery.

## Testing

We run a game day twice a year. The last one, in May 2025, met the RTO with 3 hours 10 minutes but exceeded the data-loss target on Kafka. Action items are tracked in the quarterly goals.
