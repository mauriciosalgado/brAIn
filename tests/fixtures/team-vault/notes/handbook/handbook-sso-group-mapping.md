# Single Sign-On and Group Mapping

Tags: #security #handbook

## Identity Provider

Employees authenticate through our identity provider, which federates to AWS IAM Identity Center, GitHub Enterprise (SAML), Grafana (OIDC) and PagerDuty. Sessions last 8 hours for AWS and 12 for the rest. MFA is mandatory; SMS is not an accepted factor.

## Group Naming

Groups follow `<system>-<team>-<level>`, for example `aws-platform-admin` or `gh-payments-write`. Membership is controlled by the team manager through the identity provider; direct assignments of users to AWS permission sets are not permitted because they are invisible in access reviews.

## Permission Sets

| Permission set | Max session | Used for |
|---|---|---|
| ReadOnly | 8h | everyone |
| Developer | 8h | deploy-related actions in dev/stg |
| PlatformAdmin | 4h | platform team, prod via approval |
| BreakGlass | 4h | incidents only |

## Troubleshooting Login

If `aws sso login` opens a browser but then says the device code expired, clear the cache with `rm -rf ~/.aws/sso/cache` and retry. A user who sees "no accounts available" is missing a group; check membership in the identity provider before opening a ticket.
