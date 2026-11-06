# 2025-10-14 Bad Helm Release Takes Down Ingress

Tags: #incident #helm

## Summary

A routine fortnightly platform release upgraded the ingress-nginx Helm chart on 14 October 2025. A values change mistakenly set `controller.replicaCount: 0` (a YAML key was misindented, and the intended value was dropped, but the chart's default was overridden by a leftover override). External traffic failed for 9 minutes (Sev1).

## Timeline

- 10:02 platform release PR merged; Argo CD synced staging only, production synced on approval.
- 10:21 production sync approved.
- 10:22 ingress pods terminated; no new ones created.
- 10:25 page for synthetic checks failing.
- 10:31 we reverted the PR; Argo restored 3 replicas.

## Why Staging Didn't Catch It

Staging had its own values file that set the replica count explicitly. The `helm template` rendering was only validated for the prod file by kubeconform, which doesn't flag zero replicas as invalid.

## Fixes

Added a conftest policy denying Deployments with 0 replicas in prod overlays, a PDB for the ingress with `minAvailable: 2` (which blocks eviction but not scale-to-zero, so the policy matters), and a rendered-diff comment on promotion PRs showing the final manifest diff. The release train now canary-syncs one cluster zone first.
