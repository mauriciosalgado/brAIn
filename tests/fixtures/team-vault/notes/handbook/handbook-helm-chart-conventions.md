# Helm Chart Conventions

Tags: #helm #handbook

## One Library Chart

Services do not copy-paste manifests. They depend on our `acme-service` library chart (currently 3.4.x), which renders the Deployment, Service, HPA, PDB, ServiceAccount and ServiceMonitor from a small values file. A service chart is typically under 40 lines of values.

## Values Layout

Each service repo has `values.yaml` for defaults and `values-stg.yaml` / `values-prod.yaml` for overrides. Never put secrets in values. Image tags are always set by CI, never edited by hand. Resource requests are required; a chart that omits them fails the `helm lint` custom rule.

```yaml
replicaCount: 3
image:
  repository: 123456789012.dkr.ecr.us-east-1.amazonaws.com/orders-api
  tag: ""   # set by CI
resources:
  requests: {cpu: 250m, memory: 512Mi}
  limits: {memory: 768Mi}
autoscaling: {enabled: true, minReplicas: 3, maxReplicas: 12, targetCPUUtilizationPercentage: 65}
```

## Versioning

The library chart follows semver. Breaking changes bump the major and ship with a migration note. Service charts pin the library with a `~3.4.0` range so patch releases flow automatically.

## Testing Charts

Run `helm lint`, then `helm template . -f values-prod.yaml | kubeconform -strict` in CI. For anything with hooks, install into a kind cluster using `chart-testing` (`ct install`). Hooks that run Jobs must set `ttlSecondsAfterFinished` or they accumulate.
