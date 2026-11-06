# ADR-0005: Thanos for Long-Term Metrics

Tags: #observability #decision

## Context

Local Prometheus retention of 15 days was insufficient for capacity planning and for investigating quarter-over-quarter regressions. Running a single huge Prometheus did not scale past about 8 million active series.

## Decision

Keep Prometheus per cluster but remote-write to Thanos Receive, storing blocks in S3. Grafana queries Thanos Query, which merges recent data and history. We rejected Amazon Managed Prometheus because ingestion pricing at our series volume projected to about $4,000 a month versus around $900 for Thanos infrastructure.

## Operational Impact

Thanos adds components to operate: receive, store gateway, compactor, query. The compactor must run as a singleton; two compactors corrupt blocks. We set a 13-month retention on raw data.

## Open Items

Downsampling to 5m and 1h resolutions is not enabled and makes long-range queries slow.
