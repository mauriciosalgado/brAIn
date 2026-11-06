# Runbook: Deploy to Production

Tags: #release #scripts

## Preconditions

A production deploy requires: the same image tag healthy in staging for 30 minutes, a promotion PR with rollback plan, one code owner approval, no active Sev1 or Sev2, and not being inside a change freeze. Deploys happen Tuesday to Thursday, 09:00-15:00 UTC.

## Promote

```bash
./scripts/promote.sh orders-api   # copies the staging tag into envs/prod and opens a PR
gh pr merge --squash --auto
```

Production Argo Applications are set to manual sync. After the PR merges, a person must click Sync or run `argocd app sync orders-prod`, and the rollout is a canary managed by Argo Rollouts: 10% for 10 minutes, then 50% for 10 minutes, then 100%.

## What to Watch

Keep the service dashboard open. Abort the rollout (`kubectl argo rollouts abort orders-api -n orders`) if the 5xx ratio exceeds 1%, p95 latency goes up 20%, or restarts occur. Aborting returns traffic to the stable ReplicaSet in seconds.

## Communicate

Announce start and completion in `#releases`. Add a Grafana annotation with `./scripts/annotate.sh` so graphs show the deploy time.

## Rollback

Revert the promotion PR and sync. Do not roll back database migrations; the previous version must be compatible with the new schema.

## Post-Deploy

Confirm no new alerts after 30 minutes. Watch the next on-call handover for anything pending.
