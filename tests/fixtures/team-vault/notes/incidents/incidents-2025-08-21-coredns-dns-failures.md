# 2025-08-21 Internal DNS Resolution Failures

Tags: #incident #networking

## Summary

On 21 August 2025 CoreDNS pods in `plat-prod` began timing out, producing intermittent `no such host` errors across services for 26 minutes (Sev2). External DNS in Route 53 was unaffected.

## Root Cause

CoreDNS had two replicas on `system` nodes and a `ndots:5` default in pod resolv.conf. A new batch job made 12,000 lookups per second of external hostnames, each expanded through four search domains. The CoreDNS pods hit their CPU limit of 200m and throttled.

## Mitigation

Scaled CoreDNS to 6 replicas and removed the CPU limit. Then fixed the batch job's resolv.conf with `dnsConfig: options: [{name: ndots, value: "2"}]` and trailing dots on hostnames.

## Follow-ups

Deploy NodeLocal DNSCache, which cuts upstream queries by caching on each node. Autoscale CoreDNS with the cluster-proportional-autoscaler. Alert on `coredns_dns_request_duration_seconds` p99 above 500 ms.
