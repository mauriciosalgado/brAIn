# Runbook: Back Up Kafka Topics

Tags: #backup #scripts

## What "Backup" Means for Kafka

Kafka replication (RF 3) protects against broker loss, not against a bad producer, deleted topics or a region outage. For a small set of critical topics (`orders.order-created.v1`, `payments.payment-settled.v1`) we mirror data to S3 using the Kafka Connect S3 sink so we can replay events after a logical error. Other topics are rebuildable from source systems and not backed up.

## S3 Sink Connector

The connector writes Avro files partitioned by hour:

```json
{
  "name": "s3-sink-orders",
  "connector.class": "io.confluent.connect.s3.S3SinkConnector",
  "topics": "orders.order-created.v1",
  "s3.bucket.name": "acme-prod-kafka-archive",
  "flush.size": "50000",
  "rotate.interval.ms": "600000",
  "partitioner.class": "io.confluent.connect.storage.partitioner.TimeBasedPartitioner",
  "path.format": "'dt'=YYYY-MM-dd/'hr'=HH"
}
```

Files appear within 10 minutes of production. The archive bucket keeps objects for 90 days, then moves them to Glacier for 2 years.

## Replaying a Topic

To rebuild a topic after corruption, pause consumers, create a new topic `...v1-replay`, and run the replay job that reads the S3 range and produces to it. Consumers are then switched with the new topic name through config. Do not produce into the original topic, because offsets would collide with committed consumer positions.

```bash
kubectl -n plat-kafka create job replay-orders --from=cronjob/kafka-replay \
  -- --topic orders.order-created.v1-replay --from 2025-05-20T10:00Z --to 2025-05-20T13:00Z
```

## Consumer Offsets and Configuration

Consumer group offsets are not archived. After a replay, set offsets deliberately with `kafka-consumer-groups.sh --reset-offsets --to-datetime`. Topic configuration is in Git, so topic definitions are restored by applying Terraform.

## Limits

Replay throughput is about 40 MB/s, so replaying 24 hours of orders (roughly 200 GB) takes around 80 minutes.
