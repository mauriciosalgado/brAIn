# CI/CD Pipeline Architecture

Tags: #cicd #architecture

## Overview

Code lives in GitHub; builds run on GitHub Actions. Pull requests trigger lint, unit tests, a container build and a Trivy scan. Merging to `main` publishes an image to ECR tagged with the git SHA and bumps the image tag in the `deploy-config` repository through an automated pull request. Argo CD watches that repository and syncs the cluster, so GitHub Actions never holds cluster credentials.

## Runners

We use self-hosted runners on EKS managed by actions-runner-controller. Runner pods are ephemeral, one job per pod, scale from 2 to 40, and use an IRSA role with push access to ECR only. Jobs needing Docker builds use BuildKit in rootless mode with a registry cache in ECR, cutting typical build time from 9 minutes to 3.

## Environments and Promotion

Merge to `main` auto-deploys to staging. Production deploys are promoted by merging a second PR in `deploy-config` that copies the staging tag to the production overlay. Production promotion requires one approval from a code owner and is blocked during change freezes.

## Artifact Retention

ECR lifecycle policy keeps the last 50 tagged images per repository and expires untagged images after 7 days. Build logs in GitHub are retained 90 days. SBOMs are attached to images as OCI artifacts.
