# Runbook: Deploy to Staging

Tags: #release #scripts

## Trigger

Staging deployments happen automatically on every merge to `main`: CI builds the image, opens a PR to `deploy-config` that edits `envs/stg/<service>/values.yaml`, and auto-merges it when checks pass. Argo CD syncs `plat-stg` within about 2 minutes. You only need this runbook when the automation breaks or when deploying a feature branch.

## Deploy a Feature Branch

```bash
gh workflow run build.yml --ref my-branch -f push_image=true -f deploy_env=stg
argocd app set orders-stg --helm-set image.tag=my-branch-3fa9c21
argocd app sync orders-stg
```

The override is temporary: Argo self-heal in staging reverts it after 2 hours unless the app is paused. Post in `#stg-deploys` so nobody else is surprised.

## Verify

```bash
kubectl -n orders get pods -l app=orders-api
curl -s https://orders.stg.example-corp.io/healthz
```

Run the smoke suite with `make smoke ENV=stg`, which takes 4 minutes. Staging has no change windows and no approval requirement.

## Rolling Back

Revert the `deploy-config` commit or use `argocd app rollback orders-stg`. Rollbacks in staging need no ticket.

## Data

Staging uses a database seeded from sanitized production data refreshed monthly. Never point staging at production Kafka or S3.
