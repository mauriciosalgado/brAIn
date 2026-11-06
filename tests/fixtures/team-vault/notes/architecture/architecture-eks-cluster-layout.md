# EKS Cluster Layout

Tags: #kubernetes #architecture

## Cluster Inventory

We run three EKS clusters: `plat-dev`, `plat-stg` and `plat-prod`, all on Kubernetes 1.29 at the time of writing. Dev and staging live in the nonprod AWS account (us-east-1); production lives in its own account and spans three availability zones. Each cluster has a private API endpoint only; engineers reach it through the VPN or the SSM bastion. Cluster add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI driver) are managed as EKS add-ons through Terraform so version bumps go through review.

## Node Groups

Production uses four managed node groups. `system` (3x m6i.large, on-demand) hosts CoreDNS, the ingress controller and monitoring agents, and carries the taint `dedicated=system:NoSchedule`. `general` (m6i.2xlarge, 6-24 nodes) runs stateless services. `memory` (r6i.2xlarge, 2-8 nodes) is for the JVM-heavy search indexers. `batch` is Spot-only (mixed m5/m6i/c5 families) and tolerates `workload=batch`. Nodes are replaced rather than patched: we rebuild the AMI monthly and roll the groups.

| Group | Instance | Capacity | Min/Max |
|-------|----------|----------|---------|
| system | m6i.large | on-demand | 3/3 |
| general | m6i.2xlarge | on-demand | 6/24 |
| memory | r6i.2xlarge | on-demand | 2/8 |
| batch | mixed | spot | 0/40 |

## Namespaces and Tenancy

Each product team gets one namespace per environment, named `<team>-<service-group>`. Platform namespaces are prefixed `plat-` (for example `plat-ingress`, `plat-monitoring`). Every namespace is created from a Terraform module that also installs a default-deny NetworkPolicy, a ResourceQuota (default 40 CPU requests, 80 GiB memory) and a LimitRange. Teams cannot create ClusterRoles; they get an edit role bound to their SSO group inside their own namespaces only.

## Ingress and Traffic Flow

Traffic enters through an internet-facing Network Load Balancer pointing at NGINX ingress pods in `plat-ingress`. TLS terminates at the ingress using certificates issued by cert-manager. Internal service-to-service calls use ClusterIP services and CoreDNS; we do not run a service mesh. The ingress runs 3 replicas with a PodDisruptionBudget of `minAvailable: 2` and spreads across zones with topologySpreadConstraints.

## References

- Kubernetes version policy: we stay within one minor version of the latest EKS release.
