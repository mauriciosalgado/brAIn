# DSF BaSyx Helm Chart Publish

This is a decision record for the publication of the Basyx Helm chart, outlining the challenges faced with GitHub Pages and the decision to use Amazon ECR as an alternative.

Links: [[dsf-3392.md]]
Tags: #basyx #decision #helm

---

## Table of Contents

<!-- toc -->

- [GitHub Pages](#github-pages)
  * [Conclusion](#conclusion)
- [Amazon ECR](#amazon-ecr)
  * [Set AWS Tooling Account](#set-aws-tooling-account)
  * [Create Repository](#create-repository)
  * [Publishing Helm Chart](#publishing-helm-chart)
    + [Login to ECR](#login-to-ecr)
    + [Pushing Chart to Registry](#pushing-chart-to-registry)
    + [Validate Chart in Registry](#validate-chart-in-registry)
- [Install Chart](#install-chart)
  * [CLI](#cli)
  * [ArgoCD](#argocd)
- [References](#references)

<!-- tocstop -->

---

## GitHub Pages

After setting up a `gh-pages` branch in the `dsf-basyx` repository, we can see it serves the `index.yaml` file correctly, via browser (authenticated):

![[dsf-basyx-helm-repo-pages-index.png]]

But when trying to get the `index.yaml` file from the GitHub Pages URL via curl (not authenticated), we get a 302 redirection to an authentication page:

```sh
❯ curl -I <https://pages.atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-basyx/index.yaml>

HTTP/2 302
server: GitHub.com
date: Tue, 24 Feb 2026 16:19:39 GMT
content-type: text/html
content-length: 138
location: <https://atc-github.azure.cloud.bmw/sessions/_auth_request_bounce?return_to=https%3A%2F%2Fpages.atc-github.azure.cloud.bmw%2FExtended-Enterprise-Catena-X%2Fdsf-basyx%2Findex.yaml>
```

This is confirmed when we try to add the repo to Helm, which fails with an error indicating that the URL is not a valid chart repository or cannot be reached:

```sh
❯ helm repo add dsf <https://pages.atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-basyx>

Error: looks like "<https://pages.atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-basyx>" is not a valid chart repository or cannot be reached: error converting YAML to JSON: yaml: line 38: mapping values are not allowed in this context
```

Even after using a PAT to authenticate, we still are unable to add the repository:

```sh
❯ helm repo add basyx --username qxz6fuq --password $TOKEN https://pages.atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-basyx/

Error: looks like "https://pages.atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-basyx/" is not a valid chart repository or cannot be reached: error converting YAML to JSON: yaml: line 38: mapping values are not allowed in this context
```

### Conclusion

Since our GitHub instances sit behind WebEAM.Next and helm can't handle SSO, we can't use GitHub Pages to serve our Helm chart repository.

## Amazon ECR

The recommended way to store and share chart packages is to use container registries with OCI support, so the obvious alternative is to use Amazon ECR.

See: [helm-docs-registries](https://helm.sh/docs/topics/registries/)

The following steps outline the process of creating an AWS ECR repository and publishing Basyx helm chart to it.

### Set AWS Tooling Account

```sh
export AWS_PROFILE=IDS-Dataspace-Connector-Tooling
```

### Create Repository

> [!NOTE]
> The repo name must be in the format `dsf-charts/<chart-name>`

```sh
aws ecr create-repository \
    --repository-name dsf-charts/basyx \
    --image-tag-mutability IMMUTABLE \
    --region eu-west-1
```

This creates an ECR with the following properties:

```json
{
  "repository": {
    "repositoryArn": "arn:aws:ecr:eu-west-1:207050578098:repository/dsf-charts/basyx",
    "registryId": "207050578098",
    "repositoryName": "dsf-charts/basyx",
    "repositoryUri": "207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx",
    "createdAt": "2026-02-24T21:47:47.961000+00:00",
    "imageTagMutability": "IMMUTABLE",
    "imageScanningConfiguration": {
      "scanOnPush": false
    },
    "encryptionConfiguration": {
      "encryptionType": "AES256"
    }
  }
}
```

### Publishing Helm Chart

#### Login to ECR

```sh
aws ecr get-login-password \
     --region eu-west-1 | helm registry login \
     --username aws \
     --password-stdin 207050578098.dkr.ecr.eu-west-1.amazonaws.com
```

#### Pushing Chart to Registry

```sh
❯ helm push basyx-0.1.0.tgz oci://207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts

Pushed: 207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx:0.1.0
Digest: sha256:ffc008ee23ffaaf0823ee8321729065a730160f5dae5932c9f43be19c0c4f268
```

#### Validate Chart in Registry

This retrieves the chart metadata from the registry, confirming that it was successfully published and is available for installation:

```sh
❯ helm show chart oci://207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx

Pulled: 207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx:0.1.0
Digest: sha256:ffc008ee23ffaaf0823ee8321729065a730160f5dae5932c9f43be19c0c4f268
apiVersion: v2
appVersion: 1.0.0
dependencies:
- condition: keycloak.enabled
  name: keycloak
  repository: https://charts.bitnami.com/bitnami
  version: 24.4.11
- condition: postgresql.enabled
  name: postgresql
  repository: https://charts.bitnami.com/bitnami
  version: 18.2.4
- condition: aas-registry.enabled
  name: aas-registry
  repository: file://../aas-registry
  version: 0.1.0
- condition: aas-discovery.enabled
  name: aas-discovery
  repository: file://../aas-discovery
  version: 0.1.0
description: A Helm chart for Basyx Go applications
name: basyx
type: application
version: 0.1.0
```

## Install Chart

### CLI

```sh
aws ecr get-login-password \
     --region eu-west-1 | helm registry login \
     --username aws \
     --password-stdin 207050578098.dkr.ecr.eu-west-1.amazonaws.com

helm install basyx oci://207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx -n basyx --create-namespace
```

### ArgoCD

> [!NOTE]
> We'll have to configure access to the ECR registry in ArgoCD, either with IRSA or Pod Identity

We can also use the OCI registry as a source in ArgoCD applications, thus including Basyx in our GitOps workflow.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: basyx
  namespace: argocd
spec:
  project: default
  sources:
    - repoURL: oci://207050578098.dkr.ecr.eu-west-1.amazonaws.com/dsf-charts/basyx
      path: .
      targetRevision: 0.1.0
      helm:
        valueFiles:
          - aas-discovery-configs.yaml
          - aas-registry-configs.yaml
          - $path/app-of-apps/apps/basyx/values/cluster-prod.yaml
    - repoURL: git@atc-github.azure.cloud.bmw:Extended-Enterprise-Catena-X/dsf-argo-sandbox.git
      targetRevision: master
      ref: path
  destination:
    server: https://kubernetes.default.svc
    namespace: basyx
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      prune: true
      selfHeal: true
```

---

## References

- [helm-chart-repository](https://helm.sh/docs/topics/chart_repository/)
- [aws-ecr-push-oci-artifact](http://docs.aws.amazon.com/AmazonECR/latest/userguide/push-oci-artifact.html)
- [confluence-gh-pages-discussion](https://atc.bmwgroup.net/confluence/display/AOS/questions/2038735873/answers/2073922651)

---
