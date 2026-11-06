# VPN Access

Tags: #networking #handbook

## Connecting

We use WireGuard through the company VPN client. Sign in with SSO, and the client downloads a profile that routes only 10.0.0.0/8 and the internal DNS resolver through the tunnel. Private EKS API endpoints are unreachable without it.

## Common Problems

If names under `internal.example-corp.io` fail to resolve, the DNS override did not apply; toggle the tunnel. Keys expire after 30 days and re-enroll silently at next login.
