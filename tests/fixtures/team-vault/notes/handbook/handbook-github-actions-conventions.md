# GitHub Actions Conventions

Tags: #cicd #handbook

## Workflow Structure

Reusable workflows live in the `.github` repo and are called with `uses: acme/.github/.github/workflows/build.yml@v4`. Service repos should contain a thin caller file. Pin third-party actions to a full commit SHA, not a tag, with a comment showing the version; Dependabot keeps them current.

## Permissions

Set `permissions: contents: read` at the top of every workflow and widen per job only as needed. Deployments authenticate to AWS with OIDC (`aws-actions/configure-aws-credentials` with `role-to-assume`), never with stored access keys. Long-lived keys in repository secrets are a policy violation.

## Caching and Speed

Use `actions/cache` keyed on lockfile hashes. Docker layer cache goes to ECR. Matrix builds are limited to 6 parallel jobs to avoid starving the shared runner pool. Jobs should time out explicitly with `timeout-minutes: 20`.

## Required Checks

The branch protection rules require `lint`, `test`, `build` and `trivy-scan`. Rename a job and you silently remove the required check, so change the protection rule in the same PR.

## Concurrency

Use `concurrency: group: deploy-${{ github.ref }}` with `cancel-in-progress: false` for deploy jobs, and `true` for test jobs on pull requests.
