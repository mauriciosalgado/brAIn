# VPC and Network Design

Tags: #networking #architecture

## Address Plan

Each AWS account owns a /16 carved from 10.0.0.0/8 so peering and Transit Gateway routes never overlap. Production is 10.40.0.0/16, staging 10.30.0.0/16, dev 10.20.0.0/16, and the shared-services account 10.10.0.0/16. Inside a VPC we split into /20 subnets per tier per zone: public (load balancers and NAT only), private-app (EKS nodes), and private-data (RDS, MSK). Pods get IPs from secondary CIDR 100.64.0.0/16 via VPC CNI custom networking, which is why the node subnets are not at risk of exhaustion.

## Egress and NAT

Production has one NAT gateway per availability zone so a zone failure does not cut egress for the others. Dev uses a single NAT gateway to save roughly $65 a month per extra gateway. Outbound traffic to AWS services goes through gateway endpoints for S3 and DynamoDB and interface endpoints for ECR, STS, SQS, KMS and CloudWatch Logs; this keeps image pulls off the NAT and cut our data processing bill noticeably.

## Transit Gateway and Peering

All accounts attach to one Transit Gateway in us-east-1. Route tables are segmented: prod attachments cannot route to dev. Shared-services (CI runners, VPN, Prometheus remote-write receiver) is reachable from every environment. We avoid VPC peering except for one legacy link to the analytics VPC owned by the data team, which has a static route and a security-group rule limited to port 5432.

## Security Groups and NACLs

We rely on security groups, referenced by ID rather than CIDR, and leave NACLs at the default allow. Database groups only accept traffic from the app node group's security group. Any rule opening 0.0.0.0/0 other than 443 on the public load balancer fails a Checkov policy in CI and needs a security exception ticket.
