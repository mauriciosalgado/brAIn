# 2025-09-09 Expired Internal Certificate Breaks Payments

Tags: #incident #networking

## Summary

At 06:00 UTC on 9 September 2025 the internal mTLS certificate for the payments gateway expired. Calls from the checkout service failed with `certificate has expired`, impacting card payments for 1 hour 12 minutes (Sev1).

## Why It Was Missed

This certificate was issued manually from AWS Private CA a year earlier and was not managed by cert-manager, so the `cert_expiry_days` exporter did not see it. The ticket for renewal had been assigned to an engineer who then changed teams.

## Resolution

We issued a new certificate and replaced the secret `gateway-mtls` in `payments`, then restarted the gateway pods. The first attempt failed because the new certificate used a different intermediate and the checkout trust bundle didn't include it. We updated the bundle ConfigMap and restarted checkout.

## Contributing Factors

No inventory of manually issued certificates existed. The calendar reminder went to a personal calendar.

## Actions

- Inventory every certificate in Private CA via `aws acm-pca list-certificates`, add each to the exporter. Done 12 September.
- Convert the gateway to cert-manager with the Private CA issuer.
- Trust bundles contain the CA root, never the intermediate.
- Add a 30-day certificate warning to the weekly on-call digest.
