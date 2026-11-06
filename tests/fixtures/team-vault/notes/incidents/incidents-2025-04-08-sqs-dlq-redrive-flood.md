# 2025-04-08 SQS Dead-Letter Queue Redrive Flood

Tags: #incident #aws

## Summary

After fixing a bug in the webhook delivery worker, an engineer redrove 410,000 messages from its dead-letter queue at once on 8 April 2025. The worker fleet scaled out and delivered a burst of webhooks that overwhelmed two partner endpoints, which started rate limiting us and blocked fresh webhooks for 2 hours (Sev3, partner-visible).

## What Happened

The DLQ held a week of failures. The redrive used the console's default speed (max). KEDA scaled the worker from 4 to 60 pods based on queue depth, producing about 3,000 requests per second against partner APIs that allowed 100.

## Remediation

Paused the queue by setting the worker to zero, purged nothing, and restarted the redrive with `--max-number-of-messages-per-second 50` through `aws sqs start-message-move-task`. The backlog cleared in about 2.5 hours.

## Lessons

Redrive rate must be set deliberately. Workers calling third parties need per-destination rate limits, not just autoscaling caps. The queue architecture note now warns about redrive.
