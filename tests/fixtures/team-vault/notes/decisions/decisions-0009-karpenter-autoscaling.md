# ADR-0009: Karpenter for Node Autoscaling

Tags: #kubernetes #decision

## Decision

We adopt Karpenter in dev and staging first, replacing Cluster Autoscaler for the `batch` group. Production general nodes keep managed node groups until Q1 2026.

## Rationale

Cluster Autoscaler took 3-4 minutes to add capacity because it scaled Auto Scaling Groups; Karpenter launches right-sized instances in about 60 seconds and consolidates underused nodes. Estimated saving is 12% on batch compute.

## Risks

Karpenter consolidation can evict pods unexpectedly; every workload needs a PDB and `karpenter.sh/do-not-disrupt` on jobs that cannot be interrupted.
