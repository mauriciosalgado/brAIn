# ADR-0002: Terraform Over CloudFormation

Tags: #terraform #decision

## Context

Early infrastructure was a mix of hand-clicked resources and CloudFormation stacks. Stack drift and slow rollbacks on failed updates blocked us several times. We also manage non-AWS resources (Datadog was then used, PagerDuty, GitHub teams) that CloudFormation cannot express.

## Decision

Use Terraform for all infrastructure, with S3 + DynamoDB for state. Existing stacks are imported gradually; new CloudFormation is not allowed except for AWS-provided templates such as the Control Tower baseline.

## Trade-offs

Terraform state must be protected and locked, and provider upgrades can introduce churn. In return we get plan output readable in pull requests, a large module ecosystem, and one tool across AWS, GitHub and PagerDuty. We considered Pulumi but rejected it because reviewers prefer HCL's declarative shape over general-purpose programs.

## Outcome

By the end of 2024, 94% of resources were managed in Terraform. The remainder is tracked on the quarterly goals page.
