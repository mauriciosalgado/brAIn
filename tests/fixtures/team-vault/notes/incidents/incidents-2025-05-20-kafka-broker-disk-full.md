# 2025-05-20 Kafka Broker Disk Full

Tags: #incident #kafka

## Summary

Broker 4 of the production Kafka cluster ran out of disk at 11:12 UTC on 20 May 2025. Its partitions went offline for producers using `acks=all` with min ISR 2, causing publish failures for the notifications service for 31 minutes (Sev2). No data was lost.

## Detection

The 70% disk alert fired three days earlier but only for broker 4; it was routed to a channel nobody read after a team rename. The page that occurred was for producer error rate.

## Root Cause

A new topic `notifications.delivery-log.v1` had been created with 48 partitions and default 7-day retention but received 6x the expected volume. The partition leaders were unevenly distributed, so broker 4 held 31% of the data. Local NVMe volumes cannot be extended.

## Resolution

We reduced retention on the topic to 1 day with `kafka-configs.sh --alter --add-config retention.ms=86400000`, which freed space after the next log segment roll. We then forced segment deletion by temporarily lowering `segment.ms`. A reassignment of ten partitions to brokers 2 and 6 evened out disk usage.

## Lessons

Disk alerts must go to the owning team's channel and page above 80%. Topics need a size estimate in the creation PR. Added an alert for broker disk skew above 15%.
