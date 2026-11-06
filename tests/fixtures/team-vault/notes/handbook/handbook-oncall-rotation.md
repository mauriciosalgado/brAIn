# On-Call Rotation Handbook

Tags: #oncall #handbook

## How the Rotation Works

The platform team runs a weekly primary and secondary rotation, handing over every Monday at 10:00 UTC. The rotation has eight engineers, so each person is primary roughly every eight weeks. Swaps are arranged in PagerDuty at least 24 hours ahead and posted in `#plat-oncall`. If the primary does not acknowledge a page within 5 minutes, it escalates to the secondary, then after another 10 minutes to the engineering manager.

## Expectations While Carrying the Pager

You must be able to reach a laptop with VPN within 15 minutes and be sober and alert enough to make production changes. You are not expected to fix everything alone: the goal is to stabilize, communicate and escalate. During business hours the on-call engineer works the interrupt queue instead of sprint tickets, and unplanned work should be written into the handover document.

## Handover Checklist

At handover the outgoing primary writes a short summary covering: open incidents, flaky alerts seen, silences still active and their expiry, any manual changes made outside Git, and upcoming risky changes. The incoming engineer reads the last two weeks of pages and acknowledges in the channel.

## Compensation and Rest

On-call carries a flat weekly stipend, plus time off in lieu: a page between 00:00 and 06:00 local time that takes more than 30 minutes earns a late start the next morning. If you were paged more than three times overnight, take the full next morning off.

## Reducing Noise

Every page that required no action gets a ticket labeled `alert-noise`. We review those labels in the monthly ops review and either tune the threshold or delete the alert. Our goal is fewer than 5 actionable pages per on-call week.
