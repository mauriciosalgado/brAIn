# Runbook: Debug a CrashLoopBackOff Pod

Tags: #kubernetes #scripts

## First Look

```bash
kubectl -n orders get pod orders-api-7d9f -o wide
kubectl -n orders describe pod orders-api-7d9f | sed -n '/Events/,$p'
kubectl -n orders logs orders-api-7d9f --previous --tail=100
```

`--previous` is the important flag: the current container has just restarted and may have no logs yet. Check the `Last State` and exit code: 137 is SIGKILL (usually OOMKilled), 143 SIGTERM, 1 an application error, 127 or 126 a bad command in the image.

## Common Causes

| Symptom | Likely cause | Fix |
|---|---|---|
| exit 137, reason OOMKilled | memory limit too low | raise limit, check for leaks |
| liveness probe failed | probe starts too early | add `startupProbe` |
| ImagePullBackOff | ECR auth or wrong tag | check tag exists, IRSA role |
| connection refused to DB | secret rotated, wrong password | restart pods after secret sync |
| permission denied on mounted volume | wrong fsGroup | set `securityContext.fsGroup` |

## Debug Without Changing the Pod

```bash
kubectl -n orders debug -it orders-api-7d9f --image=busybox:1.36 --target=orders-api
```

An ephemeral container shares the process namespace so you can inspect the network and files. To keep a crashing pod alive for inspection, override the command with `sleep 3600` in a copy: `kubectl debug pod/x --copy-to=x-debug --container=app -- sleep 3600`.

## Escalation

If more than one service in a namespace loops after a platform change, check the last Argo sync and `kubectl get events -A --sort-by=.lastTimestamp | tail -30` for node-level issues and treat it as an incident.
