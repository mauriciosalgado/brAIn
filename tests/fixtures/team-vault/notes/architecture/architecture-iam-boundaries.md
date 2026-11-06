# IAM Roles and Permission Boundaries

Tags: #security #architecture

## Role Types

We distinguish three kinds of IAM roles. Human roles are assumed through SSO and named `sso-<team>-<level>` (readonly, developer, admin). Workload roles are used by pods through IRSA and named `irsa-<namespace>-<service>`. Pipeline roles are assumed by GitHub Actions through OIDC federation and restricted by the `sub` claim to a specific repository and branch.

## Permission Boundaries

Teams may create their own workload roles through Terraform, but every role must carry the permission boundary `plat-team-boundary`. The boundary denies IAM user creation, changes to the CloudTrail configuration, deleting KMS keys, and anything on `*` resources in IAM. Without the boundary, the Terraform module refuses to apply.

## Service Control Policies

At the organization level, SCPs deny disabling GuardDuty, leaving the organization, and creating resources outside us-east-1 and us-west-2. The root user has MFA and its credentials are in a sealed envelope held by the security lead. An SCP is a guardrail only; it never grants access.

## Writing a Least-Privilege Policy

Start from the AWS access advisor data and CloudTrail events for the last 90 days, then use IAM Access Analyzer policy generation to draft the policy. Prefer resource ARNs over wildcards and add `aws:SourceAccount` conditions for service principals. Policies longer than 6,144 characters need splitting, a limit that surprises people.
