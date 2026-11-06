# ADR-0012: Use Argo CD for deployments

Tags: #decision #cicd

## Table of Contents

- [Status](#status)
- [Context](#context)
- [Decision](#decision)
- [Consequences](#consequences)
- [References](#references)

## Status

Accepted (2025-02-11), supersedes ADR-0004.

## Context

We deploy 40 services to three clusters. Today a GitHub Actions job runs `helm upgrade` with a long-lived
cluster credential. That credential is the most sensitive secret in our CI, and drift between what is in git and
what is in the cluster is only found by accident.

## Decision

We use Argo CD in pull mode: clusters watch a `deploy` repository and apply what is in it.

### Options considered

1. **Keep push-based Helm.** Simple, but needs credentials in CI.
2. **Flux.** Similar to Argo CD, but the UI is weaker and the team knows Argo.
3. **Argo CD.** Chosen.

## Consequences

- No cluster credentials in CI.
- Drift is detected and reported within three minutes.
- Rollbacks are a `git revert`.
- We must run and upgrade Argo CD itself.

## References

- Argo CD documentation
- ADR-0004: Push-based deploys
- Internal incident: 2024-11 bad helm release

### Notes on the references

This subsection belongs to References and must be skipped with it.
