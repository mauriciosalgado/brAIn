# Team Structure and Ownership

Tags: #team #organization

## Squads

The platform group has 11 engineers in three squads: Compute (EKS, Karpenter, ingress), Data Infrastructure (RDS, Kafka, S3 lake), and Developer Experience (CI/CD, Argo, templates). A fourth function, Security Engineering, has 2 people embedded part-time. The group is led by an engineering manager and a staff engineer for architecture.

## Service Ownership

| Area | Owning squad | Slack |
|---|---|---|
| EKS, ingress, DNS | Compute | #plat-compute |
| RDS, Kafka, backups | Data Infra | #plat-data |
| GitHub Actions, Argo, Helm library | DevEx | #plat-devex |
| IAM, secrets, access reviews | Security | #plat-sec |

## Decision Rights

Architecture decisions with cross-team impact use an ADR reviewed in the weekly architecture sync; a staff engineer breaks ties. Spending above $2,000 a month in new recurring cost requires manager approval.

## Working Agreements

Core hours are 10:00 to 16:00 in the engineer's own timezone. Pairing is encouraged for production changes. Questions go in public channels first, DMs last.
