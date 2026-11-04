# Standards

This document defines the standards for categorizing and naming notes in this knowledge base. It covers folder structure, file naming conventions and tagging strategy with some examples and a template for new documents.

> [!NOTE]
> All notes should be created in Markdown format and follow the naming and tagging conventions outlined in this document to ensure consistency and ease of navigation across our knowledge base.

## Table of Contents

<!-- toc -->

- [Structure](#structure)
- [Naming Convention](#naming-convention)
  * [Examples](#examples)
  * [Incidents Naming Convention](#incidents-naming-convention)
  * [Domains](#domains)
  * [Domain vs Tag Strategy](#domain-vs-tag-strategy)
- [Tags](#tags)
- [Document Template](#document-template)
- [Scripts & Runbooks](#scripts--runbooks)

<!-- tocstop -->

## Structure

```
notes/
├── architecture/   # How things are designed, configured, structured
├── handbook/       # How to do things, learn things, troubleshoot
├── decisions/      # Why we chose things (ADRs, rationale)
├── scripts/        # Script sharing
├── incidents/      # What went wrong (post-mortems)
└── team/           # Team-specific (dev plans, onboarding, competency charts)
```

## Naming Convention

**Pattern: `[dsf-]domain-[subdomain]-description.md`**

All lowercase. Hyphens between words.

| Part          | Required         | Description                             |
| ------------- | ---------------- | --------------------------------------- |
| `dsf-`        | if team-specific | Our configs, decisions, architecture    |
| `domain`      | yes              | Primary technology                      |
| `subdomain`   | if needed        | Component within domain                 |
| `description` | yes              | What the doc is about — conveys purpose |

### Examples

**With subdomain:**

| Filename                             | Domain | Subdomain            | Folder      |
| ------------------------------------ | ------ | -------------------- | ----------- |
| `edc-contract-negotiation-create.md` | edc    | contract-negotiation | `handbook/` |
| `aws-iam-role-create.md`             | aws    | iam                  | `handbook/` |

**Without subdomain:**

| Filename                | Domain   | Folder       |
| ----------------------- | -------- | ------------ |
| `dsf-argocd-vs-flux.md` | argocd   | `decisions/` |
| `opencode-install.md`   | opencode | `handbook/`  |

**Edge cases:**

| Filename                      | Why                                          | Folder       |
| ----------------------------- | -------------------------------------------- | ------------ |
| `dsf-eks-to-ecs-migration.md` | Multiple domains: Use primary, tag the other | `decisions/` |

### Incidents Naming Convention

Incidents are an exception — they use a **date prefix** instead of domain prefix because:

- Incidents are time-bound events
- Date prefix enables chronological sorting, which makes it easy to find "what happened on X date"

**Pattern:** `YYYY-MM-DD-domain-description.md`

| Filename                              | What it covers                        |
| ------------------------------------- | ------------------------------------- |
| `2024-01-15-eks-prod-node-failure.md` | EKS Prod node failure on Jan 15, 2024 |
| `2024-02-20-aws-outage.md`            | AWS outage on Feb 20, 2024            |
| `2025-03-10-grafana-data-loss.md`     | Grafana data loss on Mar 10, 2025     |

**Tags for incidents:**

```
Tags: #incident #domain [#affected-tools...]
```

### Domains

| Domain      | Covers             | Subdomains (for filenames)       |
| ----------- | ------------------ | -------------------------------- |
| `aws`       | AWS services       | `iam`, `vpc`, `s3`               |
| `eks`       | Amazon EKS         | `cluster`, `node-group`, `irsa`  |
| `k8s`       | Generic Kubernetes | `deployments`, `ingress`, `rbac` |
| `argocd`    | ArgoCD             | `apps`, `appsets`, `sync`        |
| `helm`      | Helm               | `charts`, `repos`, `values`      |
| `terraform` | Terraform/IaC      | `modules`, `state-file`, `vars`  |
| `edc`       | Eclipse Dataspace  | `policies`, `assets`, `catalog`  |
| `basyx`     | BaSyx AAS          | `registry`, `discovery`, `dtr`   |

### Domain vs Tag Strategy

**Rule:** The filename domain reflects the note's primary focus. Use tags for referenced tools.

| Note is about...                           | Filename starts with | Tags include           |
| ------------------------------------------ | -------------------- | ---------------------- |
| General monitoring setup that uses Grafana | `monitoring-`        | `#monitoring #grafana` |
| Grafana-specific dashboard config          | `grafana-`           | `#grafana`             |
| EKS cluster using API Gateway              | `eks-`               | `#eks #apigw`          |
| Terraform module for EKS                   | `iac-`               | `#iac #eks`            |

**Ask yourself:** "Is this note _about_ the tool, or does it just _use_ the tool?"

| Answer         | Result                  |
| -------------- | ----------------------- |
| About the tool | Tool becomes the domain |
| Uses the tool  | Tool becomes a tag      |

## Tags

Every document gets **at least two tags**: domain + type. Additional tags are encouraged for discoverability.

```
Tags: #domain #type [#optional-tags...]
```

## Document Template

> [!NOTE]
> For now, Table of Contents and Links are optional

Keep in mind the title should reflect the filename, without the "-" and with proper capitalization.

```markdown
# {{TITLE}}

Description of the note

Links: [[related-note]]
Tags: #domain #type

## Table of Contents

## Example Heading

## References
```

## Scripts & Runbooks

Notes in `scripts/` can be **runnable** via the `execute-code` plugin (a ▶ button on each code
block). Define an operation once; teammates run the vetted steps instead of re-deriving commands.
Follow these rules (start from `templates/runbook-template.md`):

- **Share state through a repo-local file, not `/tmp`.** Shell blocks are separate processes, so a first **Setup** block writes the run's non-secret config to `@vault_path/notes/scripts/env/<note>.env` (the `notes/scripts/env/` folder is gitignored). Each step block `source`s that file; a final **Cleanup** block removes it. Never use `/tmp` — it's purged after a few days, leaving steps with lost or stale state.
- **Never store secrets** in the note or the `notes/scripts/env/` file. Read them at run time from the environment or a secret tool (`aws sso login`, `~/.pgpass`, OS keychain).
- **Portable paths** via magic commands (`@vault_path`, `@note_path`) — never hardcoded absolute paths.
- **PATH append.** `execute-code` runs with Obsidian's launch PATH, which on macOS omits Homebrew dirs — so `aws`, `psql`, etc. may be "not found". The runbook template prepends `/opt/homebrew/bin:/usr/local/bin` in the Setup block to fix this portably.
