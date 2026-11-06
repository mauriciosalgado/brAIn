# Cloud Cost Management

Tags: #cost #handbook

## Budgets and Ownership

The monthly cloud bill is about $210k, split roughly EKS compute 38%, RDS 17%, data transfer 11%, S3 9%, Kafka EC2 8% and the rest shared services. Every resource must carry the tags `owner`, `env` and `cost-center`; untagged spend is reported weekly and anything untagged for 14 days is raised with the account owner. Budgets in AWS Budgets alert at 80% and 100% of forecast per team.

## Weekly Cost Review

Each Monday the on-call engineer reviews the Cost Explorer anomaly report. An anomaly is investigated if daily spend rises over 15% against the trailing 14-day average and the delta exceeds $300. Findings go in `#plat-cost`.

## Savings Levers

We hold a 1-year Compute Savings Plan covering about 60% of steady-state EKS compute; the rest stays on-demand or Spot so we can scale down. Batch workloads run on Spot with a fallback pool. Dev and staging clusters scale nodes to zero in the batch group overnight and weekends through a scheduled scaling rule, saving around $4,500 a month.

## Storage Hygiene

Unattached EBS volumes older than 7 days are snapshotted and deleted by a nightly job. EBS gp2 volumes should be migrated to gp3 (20% cheaper at the same baseline). S3 lifecycle rules are required on any bucket expected to grow past 1 TB.

## Data Transfer

Cross-AZ traffic costs $0.01 per GB each direction and surprised us when a chatty service crossed zones. Use topology-aware routing for high-volume internal services and VPC endpoints for AWS APIs to avoid NAT processing charges of $0.045 per GB.
