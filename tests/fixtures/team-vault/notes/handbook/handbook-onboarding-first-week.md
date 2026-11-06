# Onboarding: Your First Week

Tags: #onboarding #handbook

## Day One

Your manager files an access ticket before you start. On day one you receive a laptop (see the laptop setup note), your SSO account and a buddy. Sign in to SSO, enroll MFA with a hardware key or authenticator app, and accept the GitHub organization invite. You should have no production access yet; that comes after the shadowing period.

## Accounts to Request

| System | How | Typical wait |
|--------|-----|--------------|
| GitHub org + team | automatic from SSO group | minutes |
| AWS readonly | SSO permission set | same day |
| PagerDuty | buddy adds you as observer | 1 day |
| Grafana | SSO | minutes |
| VPN | self-service | minutes |

Request the developer-level AWS permission set only after week two, and admin never without an access review ticket.

## Reading List

In the first three days read the cluster layout, the VPC design note, the release process and the incident severity levels. Then read the last five post-mortems; they teach more about how things break here than any diagram.

## First Tasks

By Friday you should have: cloned the infra repo, run `terraform plan` against dev with no changes, deployed a trivial change to staging through the normal pull request flow, and shadowed one on-call handover. Your first merged PR is usually a documentation fix or a dashboard tweak.

## Shadow On-Call

Weeks 3-6 you are a shadow on the rotation: you receive pages as observer and join incident channels but make no changes. After you have shadowed two weeks and run one tabletop game day, you are added as secondary.
