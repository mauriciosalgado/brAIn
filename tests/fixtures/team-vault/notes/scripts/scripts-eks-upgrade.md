# Runbook: Upgrade EKS Cluster and Nodes

Tags: #kubernetes #scripts

## Planning

EKS minor versions are supported for about 14 months. We upgrade each cluster three times a year, dev first, then staging a week later, then production two weeks after that. Upgrade one minor version at a time; never skip. Before starting, read the Kubernetes deprecation notes for the target version and run `pluto detect-all-in-cluster` to find manifests using removed APIs.

### Pre-Flight Checklist

- All add-ons have a version compatible with the target (`aws eks describe-addon-versions --kubernetes-version 1.30`).
- No pods are stuck with PDBs of `maxUnavailable: 0`, which would block node drains.
- A recent Velero backup and Terraform state backup exist.
- The upgrade is announced in `#plat-oncall` and not scheduled on a Friday.

## Control Plane Upgrade

Change `cluster_version` in the Terraform stack and apply. The control plane upgrade takes about 25 minutes and the API remains available, though you may see brief connection resets.

```bash
cd live/acme-prod/us-east-1/eks
terraform plan -out=upgrade.tfplan
terraform apply upgrade.tfplan
aws eks describe-cluster --name plat-prod --query cluster.version
```

Rolling the control plane back is not possible. If anything is wrong, fix forward.

## Add-On Upgrades

After the control plane, upgrade the add-ons in this order: VPC CNI, CoreDNS, kube-proxy, EBS CSI driver. Do them one by one and wait for the DaemonSets or Deployments to be ready.

```bash
aws eks update-addon --cluster-name plat-prod --addon-name vpc-cni --addon-version v1.18.1-eksbuild.1 --resolve-conflicts OVERWRITE
```

`OVERWRITE` resets customizations to defaults, so keep our custom CNI settings (`AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true`) in the Terraform add-on configuration.

## Node Group Rollout

Node groups are upgraded by bumping the AMI release version and applying. The managed node group performs a rolling update with `max_unavailable_percentage = 25`. Do `system` first, then `general`, `memory`, and finally `batch`.

### Watching Progress

```bash
kubectl get nodes -L eks.amazonaws.com/nodegroup,kubernetes.io/arch --sort-by=.metadata.creationTimestamp
kubectl get pods -A --field-selector=status.phase!=Running | head
```

A `general` group with 18 nodes takes around 50 minutes. If a node does not drain within 15 minutes, find the blocker with `kubectl get pdb -A` and `kubectl describe node`.

### Stateful Workloads

Search indexers on the `memory` group are StatefulSets. Their PDB allows one pod down at a time, and each pod needs about 8 minutes to rejoin the cluster and warm up, so the group takes close to 2 hours. Don't raise `max_unavailable_percentage` for this group.

## Validation

Run the smoke suite against production, check that no pods are in `CrashLoopBackOff`, and confirm Prometheus targets are all up. Compare node count and pod count with the pre-upgrade values written in the ticket. Check that kubelet version on all nodes matches the control plane: `kubectl get nodes -o wide`.

## Rollback and Failure Handling

If new nodes fail to join, usually a bootstrap or CNI incompatibility, stop the rollout by setting the node group to the previous AMI version; the old launch template is still available until applied. For new pods that cannot get IPs, see the IP exhaustion incident. Keep old nodes cordoned but not deleted for 24 hours when possible.

## References

- AWS EKS version calendar; our own cluster layout note.
