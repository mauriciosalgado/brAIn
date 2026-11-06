# Tooling Inventory

Tags: #team #tooling

## Core Tools

| Tool | Purpose | Owner |
|---|---|---|
| GitHub Enterprise | source, Actions | DevEx |
| Argo CD 2.10 | GitOps deploys | DevEx |
| Terraform 1.7 | infrastructure | Compute |
| Prometheus / Thanos / Grafana | metrics | Compute |
| OpenSearch | logs | Data Infra |
| PagerDuty | paging | on-call lead |
| Slack | communication | all |
| Trivy, gitleaks, Checkov | scanning | Security |

## Licenses and Costs

PagerDuty costs about $2,100 a month for 14 seats; Grafana is self-hosted OSS. GitHub Enterprise seats are billed per user.

## Not Used

We do not use Datadog, Splunk, Jenkins, Ansible Tower, Consul or Istio. Previous experiments with Istio ended in 2023 because of sidecar overhead.
