# Runbook: Rotate TLS Certificates

Tags: #networking #scripts

## Scope

Public ingress certificates renew automatically via cert-manager. This runbook is for the cases that do not: the Kafka listener certificates from AWS Private CA (one-year validity), the internal mTLS certificates for the payments gateway, and any ingress certificate stuck in a failed renewal.

## Check Expiry

```bash
kubectl get certificate -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,READY:.status.conditions[0].status,EXP:.status.notAfter
echo | openssl s_client -connect api.prod.example-corp.io:443 -servername api.prod.example-corp.io 2>/dev/null | openssl x509 -noout -enddate
```

The `cert_expiry_days` metric alerts at 21 days (warning) and 7 days (critical).

## Force Renewal of a cert-manager Certificate

```bash
cmctl renew api-tls -n plat-ingress
cmctl status certificate api-tls -n plat-ingress
```

If the order is stuck, inspect the Challenge resource: DNS-01 failures are almost always IAM permissions on the Route 53 zone or a missing `_acme-challenge` delegation.

## Rotating Kafka Listener Certificates

Issue the new certificate from Private CA, then roll brokers one at a time, waiting for under-replicated partitions to return to 0 between brokers (about 5 minutes each). Rolling all six takes roughly an hour. Clients trust the CA, not the leaf, so they need no change unless the CA itself is rotating.

## Rollback

Keep the previous secret version: `kubectl get secret api-tls -o yaml > api-tls-backup.yaml` before replacing. If clients see handshake errors after a swap, restore the old secret and restart the ingress pods.

## Notes

Remember that a certificate renewal does not renew the key pinned by some partner integrations; tell the partner contact two weeks ahead.
