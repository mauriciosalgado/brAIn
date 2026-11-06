---
title: Platform sync 2025-03-04
date: 2025-03-04
tags:
  - meeting
  - platform
attendees: [Ana, Ben, Chidi, Dara]
---

# Platform sync 2025-03-04

> [!info] Context
> Weekly sync. Notes are rough, see [[team-meeting-cadence|the cadence note]] for the format.
> Previous notes: [[2025-02-25 platform sync]] and ![[standup-template.png]]

## Agenda

- [x] Review last week's actions
- [ ] Decide on the Karpenter rollout window
- [ ] Cost report for #finops (==over budget by 12%==)
- [-] Skip: hiring update (moved to Thursday)

## Discussion

### Karpenter rollout

Ben: we should roll out on **Tuesday** because Monday has the release freeze. Dara disagreed: `NodePool` limits
are not tuned yet. %% TODO: ask Chidi about spot interruption numbers %%

```dataview
TABLE status, owner
FROM "decisions"
WHERE contains(file.name, "karpenter")
SORT file.mtime DESC
```

> [!warning] Risk
> If the consolidation policy is `WhenEmpty` we keep paying for idle nodes.
> If it is `WhenUnderutilized` pods get evicted more often.

### Cost report

| Team | Budget | Actual | Delta |
|:-----|-------:|-------:|------:|
| Platform | 12,000 | 13,440 | +12% |
| Data | 8,000 | 7,100 | -11% |

## Actions

1. Ben to write the rollout plan ^action-ben
2. Dara to tune `NodePool` limits
   - start with `cpu: 200`
   - revisit after one week
3. Ana to schedule the retro #retro #q1

---

Next meeting: 2025-03-11
