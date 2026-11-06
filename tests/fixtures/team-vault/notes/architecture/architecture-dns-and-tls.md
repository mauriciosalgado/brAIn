# DNS and TLS Architecture

Tags: #networking #architecture

## DNS Zones

Public DNS for `example-corp.io` is hosted in Route 53 in the shared-services account. Each environment delegates a subdomain: `stg.example-corp.io` and `prod.example-corp.io` live in their own hosted zones, managed by Terraform. Private resolution inside VPCs uses a private hosted zone `internal.example-corp.io` associated with every VPC. Default TTL is 300 seconds; records for failover endpoints use 60 seconds.

## External DNS

ExternalDNS runs in each cluster with permission restricted to its own environment's zone. It creates records from Ingress annotations, using a TXT ownership marker `heritage=external-dns,owner=plat-prod`. Humans should not edit those records by hand because ExternalDNS will revert them within a minute.

## Certificates

Public certificates come from Let's Encrypt via cert-manager using the DNS-01 challenge against Route 53. Certificates are issued for 90 days and renewed when 30 days remain. Internal mTLS and Kafka listeners use certificates from a private CA hosted in AWS Private CA with one-year validity. A Prometheus exporter publishes days-to-expiry for every certificate secret.

## Load Balancer Certificates

Public NLBs do not hold certificates since TLS terminates at ingress. The few ALBs we keep for legacy apps use ACM certificates, which renew automatically as long as the DNS validation CNAME remains in the zone. Deleting that CNAME silently breaks renewal.
