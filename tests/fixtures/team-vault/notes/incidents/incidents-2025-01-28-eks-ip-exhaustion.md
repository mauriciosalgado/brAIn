# 2025-01-28 EKS Pods Stuck: Subnet IP Exhaustion

Tags: #incident #kubernetes

## Summary

During a traffic ramp on 28 January 2025 new pods stayed in `ContainerCreating` with `failed to assign an IP address to container`. The `plat-prod` cluster could not scale for 55 minutes, and the search API breached its SLO (Sev2).

## Root Cause

The VPC CNI assigns a VPC IP to every pod. Prior to custom networking, the private-app subnets were /22 (1,019 usable IPs each) and the warm IP target of the CNI kept 2 spare ENIs per node, so many addresses were held idle. At 14:10 one zone's subnet reached 0 free addresses.

## Fix

Immediately, we cordoned nodes in the exhausted zone and shifted capacity into the others. Then we set `WARM_IP_TARGET=5` and `MINIMUM_IP_TARGET=10` to cut idle reservations. The permanent fix, delivered two weeks later, was custom networking with pods drawing from 100.64.0.0/16.

## Lessons

Alert on subnet free IPs below 15%. Capacity planning must include pod IPs, not only nodes. Prefix delegation was evaluated and rejected for this cluster because of fragmented subnets.
