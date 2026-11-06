# ADR-0004: Argo CD for Deployments

Tags: #cicd #decision

## Context

Originally GitHub Actions ran `helm upgrade` against the clusters, which required cluster-admin credentials in CI. A leaked token would have meant full cluster compromise, and we had no continuous reconciliation: manual `kubectl edit` changes lived on forever.

## Decision

Adopt Argo CD in a pull model. CI only builds and updates a Git repository; Argo applies changes. Argo runs with an `app-of-apps` pattern, one Application per service per environment, with automated sync and self-heal enabled in staging and sync on manual approval in production.

## Alternatives

Flux was a close second. We picked Argo for the UI, which helps developers see rollout status without kubectl, and for ApplicationSets. Spinnaker was judged too heavy.

## Consequences

Drift is automatically reverted, which at first annoyed engineers debugging with `kubectl edit`; the fix is to pause the Application sync. Secrets must not be in Git, so we use the External Secrets Operator instead of Helm-managed secrets.
