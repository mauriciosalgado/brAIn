# Runbook: Kafka Partition Reassignment

Tags: #kafka #scripts

## When Needed

After adding brokers, or when a broker holds a disproportionate share of partitions (disk imbalance above 15%), spread partitions across the cluster. Here "partition" means a Kafka topic partition, not a disk or Postgres table partition.

## Generate a Plan

```bash
kafka-reassign-partitions.sh --bootstrap-server kafka-1:9094 --command-config admin.properties \
  --topics-to-move-json-file topics.json --broker-list "1,2,3,4,5,6,7,8" --generate
```

Save the proposed output to `plan.json`. Review it: the rack-aware assignment should keep replicas in distinct zones.

## Throttle and Execute

Throttle replication so production traffic is not starved. We use 50 MB/s per broker:

```bash
kafka-reassign-partitions.sh --bootstrap-server kafka-1:9094 --command-config admin.properties \
  --reassignment-json-file plan.json --execute --throttle 52428800
```

Moving 1 TB at that throttle takes about 6 hours. Do a batch of at most 200 partitions at a time.

## Verify and Remove the Throttle

```bash
kafka-reassign-partitions.sh ... --reassignment-json-file plan.json --verify
```

`--verify` also removes throttles when done; forgetting this leaves replicas throttled forever and causes under-replicated partitions later. Confirm `UnderReplicatedPartitions` is 0 in Grafana.

## Cancelling

To cancel in-flight moves use `--cancel` with the same plan file; partially moved partitions revert to their original replicas.
