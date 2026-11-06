# 2025-07-02 Replica Lag Cascade and Accounts Outage

Tags: #incident #postgresql

## Summary

On 2 July 2025 a long-running analytical query on the `accounts` read replica caused replication conflicts and lag that reached 38 minutes. The reporting service then fell back to the primary, saturating its connections, and login failed for 22 minutes (Sev2). The primary database itself never went down; the outage was from connection exhaustion.

## Timeline

- 13:05 a finance export started a 40-minute query on the replica.
- 13:20 lag crossed 60 seconds; warning alert fired and was silenced as noise.
- 13:41 reporting's fallback logic redirected all reads to the primary; connection count hit 500.
- 13:44 PgBouncer queue grew, login timeouts began, page fired.
- 13:52 reporting service scaled to zero; connections drained.
- 14:07 login recovered; the replica caught up by 15:30.

## Root Cause

`max_standby_streaming_delay` was set to 30 minutes on the replica, letting queries delay WAL replay. The reporting client had a primary fallback with no concurrency cap. The warning silence had been left for a prior test without expiry.

## Contributing Factors

Nobody owned the replica alert. The runbook for lag did not mention the fallback behavior.

## Action Items

- Reduce `max_standby_streaming_delay` to 60s and use `hot_standby_feedback=on`.
- Remove fallback-to-primary in reporting; fail fast with an error.
- Limit connections per client user with `ALTER ROLE ... CONNECTION LIMIT 50`.
- Enforce 24-hour maximum silence duration.
