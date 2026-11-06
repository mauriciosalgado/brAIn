# ADR-0001: Use EKS Rather Than ECS

Tags: #kubernetes #decision

## Context

In 2023 we ran 30 services on ECS Fargate. Costs were rising, teams wanted sidecars and custom schedulers, and hiring engineers with Kubernetes experience was easier than for ECS. Fargate also limited us to 16 vCPU tasks and had no way to run privileged DaemonSets for log collection.

## Decision

Move all services to Amazon EKS with managed node groups. Fargate is retained only for two low-traffic cron jobs. We chose EKS over self-managed Kubernetes on EC2 because the control plane upgrade burden is not worth the savings.

## Alternatives Considered

ECS on EC2 would have solved the cost issue but not the ecosystem one (Helm, Argo CD, operators). Nomad was rejected because no one on the team had operated it. Self-managed kubeadm clusters were rejected on operational load.

## Consequences

We took on the cost of learning cluster upgrades, which happen three times a year. The EKS control plane costs $73 per cluster per month. Compute dropped about 22% after right-sizing and Savings Plans. Migration finished in 5 months, completed March 2024.

Status: accepted.
