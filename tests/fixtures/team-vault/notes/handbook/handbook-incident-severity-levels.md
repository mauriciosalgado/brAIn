# Incident Severity Levels

Tags: #incident #handbook

## Definitions

| Level | Meaning | Example | Response |
|-------|---------|---------|----------|
| Sev1 | Customer-facing outage or data loss | checkout down | page immediately, incident commander, status page within 15 min |
| Sev2 | Major degradation, workaround exists | search slow, 20% errors | page, status page within 30 min |
| Sev3 | Minor impact or internal tooling | CI runners stuck | Slack, handled in business hours |
| Sev4 | Cosmetic or no impact | dashboard typo | ticket |

## Incident Roles

For Sev1 and Sev2 we name an incident commander (IC), a communications lead and a scribe. The IC does not type commands; they coordinate and decide. The first responder is IC until someone else explicitly accepts the role in the channel.

## Timeline and Communication

Open a channel named `#inc-YYYYMMDD-short-name`. Post updates every 30 minutes for Sev1 and every 60 for Sev2 even if nothing changed. Customer support receives a summary from the communications lead, not from the engineers.

## Post-Mortems

Sev1 and Sev2 incidents require a blameless post-mortem within five business days, published in the vault under `incidents/`. Each one must list contributing factors, what went well, and action items with owners and due dates. Action items from the last quarter are reviewed at the ops review.
