# Observability Stack

Tags: #observability #architecture

## Metrics Pipeline

Each EKS cluster runs Prometheus (kube-prometheus-stack) with 2 replicas and a 6-hour local retention. Prometheus remote-writes to Thanos Receive in the shared-services account, where metrics are kept in S3 for 13 months. Scrape interval is 30 seconds by default; high-cardinality jobs are limited to 60 seconds. Anything with more than 500,000 active series per target needs sign-off from the platform team.

## Dashboards

Grafana is the single dashboard tool, authenticated through our SSO. Dashboards are stored as JSON in Git and provisioned by a sidecar; changes made in the UI are not persisted. Every service gets a standard "RED" dashboard (rate, errors, duration) generated from a Jsonnet template, and the folder structure mirrors teams.

## Logs and Traces

Application logs are written as JSON to stdout, collected by Fluent Bit and shipped to OpenSearch with 30 days retention; audit logs go to S3 for a year. Traces use OpenTelemetry SDKs sending OTLP to a collector DaemonSet, which forwards to Tempo with a 5% head sampling rate and 100% for errors.

## Alert Routing

Alertmanager routes by the `team` label. Severity `critical` goes to PagerDuty, `warning` goes to the team's Slack channel, and `info` is dashboard-only. Inhibition rules suppress node-level warnings when a whole zone is flagged unhealthy. Silences should be created with an expiry and a ticket reference.

## Known Limitations

Thanos queries over ranges longer than 30 days are slow because we have no downsampling configured yet; it is on the roadmap. Fluent Bit drops lines larger than 256 KB.
