# 2025-03-12 RDS Storage Exhaustion on orders-prod

Tags: #incident #postgresql

## Summary

On 12 March 2025 the `orders-prod` RDS instance ran out of storage at 09:38 UTC, went read-only for writes, and checkout failed for 47 minutes (Sev1). The 1 TB volume had reached its autoscaling ceiling because the ceiling was configured at 1 TB, not 2 TB as documented.

## Timeline

- 08:50 free storage alarm (warning, below 20%) fired in Slack and was acknowledged but not acted on.
- 09:38 free storage hit zero; the database entered `storage-full` state.
- 09:44 page for 5xx ratio above 5%; incident declared.
- 09:58 storage increased to 1.5 TB with `aws rds modify-db-instance --allocated-storage 1536 --apply-immediately`.
- 10:25 writes recovered after the instance finished storage optimization.

## Root Cause

A nightly job introduced three weeks earlier wrote full audit payloads into an `order_events` table with no retention, growing 18 GB a day. Storage autoscaling was enabled but its maximum had been set to 1000 GB in Terraform, so it could not grow. The critical alert threshold (10%) was below the point at which the growth rate gave any reaction time.

## What Went Well

The restore of service was fast once the right action was identified, and the on-call engineer posted frequent updates.

## Action Items

1. Raise autoscaling ceiling to 2 TB and make Terraform the only source. Done 14 March.
2. Add alert on predicted full within 48 hours using `predict_linear`.
3. Partition `order_events` by month and drop partitions older than 90 days.
4. Warning alerts to Slack must have an owner who responds in 30 minutes.
