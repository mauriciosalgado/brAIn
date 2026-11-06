# ADR-0008: Trunk-Based Development

Tags: #engineering #decision

## Context

Long-lived `develop` and `release/*` branches produced painful merges and a release a month. Incidents traced to untested merge combinations in three of the previous six quarters.

## Decision

Everyone works from short-lived branches off `main`, merged within two days. Incomplete features hide behind runtime flags managed in a flag service. `main` must always be deployable; a broken `main` is a stop-the-line event and the author or on-call reverts within 30 minutes.

## Consequences

Deploy frequency rose from monthly to about 25 deploys per day across services. Reviewers must get used to smaller PRs. Flags need cleanup: every flag has an owner and a removal date in its description, enforced by a weekly report.
