# Quarterly Access Reviews

Tags: #security #handbook

## Purpose and Scope

Every quarter we confirm that people and machines still need the access they hold. The review covers AWS permission sets, GitHub team membership, PagerDuty, Grafana admin, database users and third-party vendor accounts. It exists to satisfy our SOC 2 control CC6.2 and to catch drift from role changes.

## Running the Review

The security lead opens a ticket in the first week of January, April, July and October. Export current memberships with the `access-export` script into a spreadsheet; each system owner marks every row `keep` or `remove`. Reviewers cannot review their own access; managers review their reports.

## Deadlines

Owners have 10 business days to respond. Rows with no response after that are removed automatically, and the removal is reversible through a normal access request. Evidence (export, decisions, removal confirmation) is stored in the compliance bucket for 3 years.

## Break-Glass Access

Break-glass admin access to production is requested through a ticket, approved by the on-call manager, and expires after four hours. Each use is reviewed the next business day with CloudTrail evidence attached.

## Offboarding

When someone leaves, HR triggers the offboarding workflow: SSO is disabled within one hour, which cuts off AWS and GitHub, and the owner of any personal access tokens or shared vendor logins rotates them within 24 hours.
