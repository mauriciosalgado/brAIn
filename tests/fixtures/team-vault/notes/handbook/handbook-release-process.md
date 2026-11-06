# Release Process

Tags: #release #handbook

## Release Cadence

Services deploy continuously to staging. Production releases happen Tuesday through Thursday between 09:00 and 15:00 UTC; we avoid Fridays and the day before a public holiday. The platform itself (cluster add-ons, ingress, observability) ships on a fortnightly train, every second Wednesday.

## Release Steps

1. Confirm the staging deployment has been healthy for at least 30 minutes and smoke tests passed.
2. Open the promotion PR in `deploy-config` and fill in the template: change summary, rollback plan, linked ticket.
3. Get the code owner approval; post in `#releases` with the PR link.
4. Merge. Argo CD syncs with a canary: 10% of pods for 10 minutes, then 50%, then 100%.
5. Watch the service dashboard: error rate must stay under 1% and p95 latency within 20% of baseline.

## Rollback

Rollback is a revert of the promotion PR, which brings the previous image tag back within about three minutes. Do not use `kubectl rollout undo` in production as Argo would flip it back. Database migrations must be backward compatible for one release so a rollback never needs a schema change.

## Change Freezes

Freezes are announced in `#releases` and apply to the last two weeks of the fiscal quarter and Black Friday week. During a freeze only fixes for Sev1 or Sev2 incidents may ship, with approval from the engineering manager.

## Hotfixes

A hotfix branches from the currently deployed tag, not from `main`. It still passes CI but may skip the 30-minute staging soak when an incident commander approves.
