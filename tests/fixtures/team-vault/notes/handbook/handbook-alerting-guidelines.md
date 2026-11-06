# Alerting Guidelines

Tags: #observability #handbook

## Principles

Alert on symptoms users feel, not on causes. A page must be actionable, urgent, and require a human. Anything else is a Slack warning or a dashboard. Every alert needs a `runbook_url` annotation linking to a note in this vault.

## Standard Thresholds

| Signal | Warning | Critical |
|--------|---------|----------|
| HTTP 5xx ratio (5m) | > 1% | > 5% |
| p95 latency vs baseline | +50% | +100% |
| Kafka consumer lag | > 50k for 10m | > 100k for 10m |
| RDS free storage | < 20% | < 10% |
| Replica lag | > 30s | > 60s for 5m |
| Pod restarts (15m) | > 3 | > 8 |
| Certificate days left | < 21 | < 7 |

## Writing a Rule

Use `for:` durations to avoid flapping, usually 5 minutes. Use burn-rate alerts for SLOs: a 14.4x burn over 1 hour and 5 minutes pages; a 6x burn over 6 hours warns. Labels must include `team` and `severity`.

```yaml
- alert: HighErrorRatio
  expr: sum(rate(http_requests_total{code=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service) > 0.05
  for: 5m
  labels: {severity: critical, team: payments}
  annotations:
    runbook_url: https://wiki.example-corp.io/runbooks/high-error-ratio
```

## Silences

Create silences in Alertmanager with a maximum duration of 24 hours unless a ticket justifies longer. The silence comment must include the ticket ID and your name.
