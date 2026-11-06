# Laptop Setup

Tags: #onboarding #handbook

## Install List

Install Homebrew, then `brew install awscli kubectl helm terraform tfenv k9s jq yq kubeconform pre-commit`. Install Docker Desktop alternative Colima for local containers. Enable full-disk encryption and the managed endpoint agent before touching any repo.

## Configuration

Run `aws configure sso` with the start URL from the SSO note and profile names `acme-dev`, `acme-stg`, `acme-prod`. Run `aws eks update-kubeconfig --name plat-dev --profile acme-dev` to get cluster access. Install pre-commit hooks in each repo with `pre-commit install`.
