# ADR-0003: Self-Managed Kafka Versus Amazon MSK

Tags: #kafka #decision

## Context

We needed to replace a single-node Kafka that was a single point of failure. Two options: Amazon MSK or a self-managed cluster on EC2. Peak throughput is 85 MB/s in, retention 7 days, about 14 TB of replicated data.

## Cost Comparison

An MSK cluster of 6 kafka.m5.2xlarge brokers with 4 TB EBS each came to roughly $9,800 a month. Self-managed on i3en.xlarge with local NVMe came to about $5,100 including the EC2 controllers, and gives about 3x the disk throughput.

## Decision

Run Kafka ourselves on EC2, with KRaft mode and Ansible-baked AMIs. We accepted the operational burden because the team already had two engineers with broker experience and the cost difference is above $55k a year.

## Revisit Criteria

Re-evaluate MSK if we lose both experienced engineers, if MSK Serverless pricing drops under $6k for our workload, or if we need multi-region replication that MSK Replicator would handle. Review date: January 2026.

## Downsides We Accept

Local NVMe storage is ephemeral: replacing a broker means re-replicating all its data from peers, which takes about 3 hours per 2 TB broker.
