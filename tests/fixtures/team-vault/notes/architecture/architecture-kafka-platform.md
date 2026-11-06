# Kafka Platform Architecture

Tags: #kafka #architecture

## Cluster Topology

Production Kafka is a self-managed 6-broker cluster on EC2 (i3en.xlarge, local NVMe) spread two per availability zone, with `broker.rack` set to the zone so replicas land in different zones. We run KRaft mode with three dedicated controllers on t3.large. Kafka version is 3.6. Replication factor is 3 and `min.insync.replicas=2` for every topic except metrics, which use RF 2. Staging is a 3-broker cluster with RF 2.

## Topic Conventions

Topics are named `<domain>.<entity>.<version>`, for example `orders.order-created.v1`. Partition counts are chosen at creation as a multiple of 6 so they divide evenly across brokers; the default is 12. Default retention is 7 days (`retention.ms=604800000`); compacted topics are explicitly marked and use `cleanup.policy=compact`. Topic creation is declarative through a Git repo and a Terraform provider; `auto.create.topics.enable` is false.

## Producers and Consumers

Producers must set `acks=all`, `enable.idempotence=true` and `compression.type=zstd`. Consumers use cooperative-sticky assignment and commit offsets manually after processing. A consumer group lagging beyond 100,000 messages for 10 minutes pages the owning team (see the alerting guidelines). Schema changes go through the schema registry with BACKWARD compatibility enforced.

## Security

Clients authenticate with SASL/SCRAM-SHA-512 over TLS on port 9094; each service has its own principal and ACLs scoped to its topics and group prefix. Inter-broker traffic is TLS on 9093. The listener certificate comes from our internal CA and is rotated yearly.

## Capacity Notes

Brokers sit at around 55% of disk. We alert at 70% and treat 80% as an incident because the broker stops accepting writes shortly after. Cluster peak throughput is about 85 MB/s in and 240 MB/s out. Adding brokers requires a partition reassignment afterwards, described in the reassignment runbook.
