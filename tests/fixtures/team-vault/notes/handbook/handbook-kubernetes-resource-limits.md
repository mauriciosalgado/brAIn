# Kubernetes Requests and Limits

Tags: #kubernetes #handbook

## Requests Versus Limits

The scheduler uses requests to place pods; limits are enforced at runtime. A pod's memory limit overrun gets it OOMKilled, whereas CPU over the limit is merely throttled. Our rule: set CPU requests, do not set CPU limits for latency-sensitive services, always set memory limits equal to or slightly above memory requests.

## Sizing Guidance

Start from observed p95 usage over two weeks plus 20% headroom. The Vertical Pod Autoscaler runs in recommendation-only mode and its suggestions are visible in Grafana's "Right-sizing" dashboard. JVM services should set `-XX:MaxRAMPercentage=75` so heap respects the container limit.

## Quality of Service

Pods with requests equal to limits are Guaranteed and evicted last under node pressure. Most services are Burstable. Pods without any requests are BestEffort and are forbidden by an admission policy.

## Horizontal Autoscaling

HPAs scale on CPU at 65% target with a stabilization window of 300 seconds on scale-down. Services consuming queues use KEDA scaling on queue depth or Kafka lag. Never run an HPA and a fixed `replicas` field together in Helm values; Argo will fight the HPA.
