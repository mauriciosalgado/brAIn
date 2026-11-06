# Runbook: Create a Prometheus Silence

Tags: #observability #scripts

## Command Line

```bash
amtool silence add alertname="HighErrorRatio" service="orders" \
  --duration=2h --author="$USER" --comment="PLAT-4821 planned load test" \
  --alertmanager.url=https://alertmanager.shared.example-corp.io
amtool silence query --expired=false
```

Expire it early with `amtool silence expire <ID>`. Maximum 24 hours without a ticket.
