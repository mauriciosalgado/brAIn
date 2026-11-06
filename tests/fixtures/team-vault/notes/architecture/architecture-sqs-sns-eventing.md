# SNS and SQS Eventing Patterns

Tags: #aws #architecture

## When We Use SQS Instead of Kafka

Kafka carries high-volume domain events with replay needs. SQS is used for work queues where each message is processed once by one worker pool and replay is not required: email sending, PDF rendering, webhook delivery. SQS standard queues are the default; FIFO queues are used only when ordering per entity matters and throughput stays under 300 messages per second per group set.

## Fan-out with SNS

For events consumed by several systems, a producer publishes to an SNS topic and each consumer owns an SQS queue subscribed to it with raw message delivery enabled. Subscription filter policies on `eventType` keep consumers from receiving what they discard. Topic and queue policies allow only the specific account and source ARN.

## Visibility and Retries

Default visibility timeout is 6x the p99 processing time, minimum 60 seconds. Workers extend visibility for long jobs rather than raising the timeout globally. Queues use a redrive policy with `maxReceiveCount=5` into a dead-letter queue retained 14 days.

## Dead-Letter Queues

Each DLQ has a CloudWatch alarm on `ApproximateNumberOfMessagesVisible > 0` for 5 minutes that notifies the owning team in Slack. Redriving is done with the SQS console "start DLQ redrive" or `aws sqs start-message-move-task` after the bug is fixed. Never redrive before fixing the cause; we have flooded a service that way.

## Encryption

Queues use SSE-KMS with the environment key. Producers therefore need `kms:GenerateDataKey` and consumers `kms:Decrypt`, a frequent cause of AccessDenied on new services.
