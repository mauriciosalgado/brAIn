---
aliases: [TLS runbook, cert rotation]
cssclasses: wide
---

# Certificate rotation

Tags: #security #tls

This note explains how we rotate certificates[^1]. The short version is in [the checklist][checklist].

## TOC

- [Why](#why)
- [How](#how)

## Why

Certificates expire. An expired mTLS certificate caused an outage in September[^2], which is why rotation is
now calendar-driven and not memory-driven.

## How

Rotate 30 days before expiry. See [the cert-manager docs][cm] for the issuer configuration, and use the
[internal CA][ca] for service-to-service certificates only.

## Notes

[^1]: Certificates here means X.509 certificates for TLS, not code signing.
[^2]: See the incident note for 2025-09-09.

[checklist]: https://wiki.example.com/tls/checklist "Rotation checklist"
[cm]: https://cert-manager.io/docs/
[ca]: https://wiki.example.com/tls/internal-ca

## References

- RFC 5280
- Internal CA policy
