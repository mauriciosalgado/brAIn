# Incident 2025-06-02: checkout latency

Tags: #incident #postmortem

## Summary

Checkout p99 latency rose from 400 ms to 9 s for 47 minutes. Root cause: a connection pool setting in the
orders service was lowered during a "cleanup" change.

## Timeline

| Time (UTC) | Event | Who |
|---|---|---|
| 09:02 | Deploy `orders-api` v2.41 (pool size `max=5`) | CI |
| 09:11 | Alert: `HighLatencyP99` fires for `checkout` | Pager |
| 09:14 | Ana acknowledges, starts a call | Ana |
| 09:20 | Looked at `SELECT count(*) FROM pg_stat_activity WHERE state = 'active' \| wc -l` (escaped pipe) | Ana |
| 09:31 | Suspects the DB; replica lag is normal | Ben |
| 09:40 | Found `max=5` in the rendered Helm values: `pool: { max: 5, min: 1 }` | Chidi |
| 09:49 | Rolled back to v2.40 | Ben |

## Impact

| Metric | Before | During | After |
|--------|--------|--------|-------|
| p99 latency | 400 ms | 9,000 ms | 410 ms |
| Error rate | 0.1% | 6.8% | 0.1% |
| Orders lost | 0 | ~310 | 0 |
| Notes | | cart abandonment rose<br>from 3% to 11% | |

## Wide table

| Component | Owner | Runbook | Dashboard | Alert | SLO target | Last reviewed | Escalation path | Notes |
|---|---|---|---|---|---|---|---|---|
| orders-api | platform | scripts-deploy-production | grafana/orders | HighLatencyP99 | 99.5% | 2025-05-01 | platform > cto | pool size matters, see the incident above |
| payments-api | payments | scripts-deploy-production | grafana/payments | PaymentErrors | 99.9% | 2025-04-12 | payments > cto | has its own database |

## What went well

- The rollback was fast once the cause was known.

## What went badly

- The alert named the symptom, not the cause.
- Nobody owned the Helm values review.

## Action items

- [ ] Add a pool-size check to the chart linter
- [ ] Alert on `pg_stat_activity` saturation
