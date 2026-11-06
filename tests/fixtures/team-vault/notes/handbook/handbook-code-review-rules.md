# Code Review Rules

Tags: #engineering #handbook

## Who Must Approve

Every change needs at least one approving review from a CODEOWNERS member; changes to Terraform in `prod/` or to IAM modules need two, one of whom is on the platform team. Authors cannot approve their own PRs, and approvals are dismissed when new commits are pushed to files the reviewer had flagged.

## Size and Scope

Aim for PRs under 400 changed lines excluding generated files and lockfiles. Larger changes should be split or accompanied by a design note. Mixing a refactor with a behavior change is not allowed; reviewers will ask to separate them.

## Review Turnaround

The expected first response time is 4 working hours. If a PR is waiting longer than one business day, ping the `#plat-reviews` channel. Reviewers use prefixes: `nit:` is optional, `question:` needs an answer but not a change, `blocker:` must be resolved before merge.

## What Reviewers Check

For infrastructure code: does `terraform plan` output match the description, are there destroys or replacements, are resources tagged with `owner` and `env`, are secrets absent. For Helm and Kubernetes manifests: resource requests and limits present, probes defined, PodDisruptionBudget for anything with more than one replica. For scripts: `set -euo pipefail`, no hardcoded account IDs, idempotent behavior.

## Merging

We squash-merge and the PR title becomes the commit message, following the conventional commits format (`feat:`, `fix:`, `chore:`). Never merge with failing required checks; if a check is flaky, file a ticket and re-run, do not bypass.
