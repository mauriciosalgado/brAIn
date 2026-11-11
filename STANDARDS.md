# Standards

This document defines the standards for categorizing and naming notes in this knowledge base. It covers folder structure, file naming conventions, tagging strategy, how a note is laid out and how to write one. Start new notes from a file in `templates/`.

> [!NOTE]
> All notes should be created in Markdown format and follow the naming and tagging conventions outlined in this document to ensure consistency and ease of navigation across the knowledge base. These are good defaults: adjust the folders and types to suit you, and keep them consistent.

## Table of Contents

<!-- toc -->

- [Structure](#structure)
- [Naming Convention](#naming-convention)
  * [Examples](#examples)
  * [Incidents Naming Convention](#incidents-naming-convention)
  * [Domains](#domains)
  * [Domain vs Tag Strategy](#domain-vs-tag-strategy)
- [Tags](#tags)
- [Title and Structure](#title-and-structure)
- [Writing Notes](#writing-notes)
- [Scripts & Runbooks](#scripts--runbooks)

<!-- tocstop -->

## Structure

```
notes/
├── architecture/   # How things are designed, configured, structured
├── handbook/       # How to do things, learn things, troubleshoot
├── decisions/      # Why things were chosen (ADRs, rationale)
├── scripts/        # Script sharing
├── incidents/      # What went wrong (post-mortems)
└── team/           # People and process (plans, onboarding, working agreements)
```

## Naming Convention

**Pattern: `[team-]domain-[subdomain]-description.md`**

All lowercase. Hyphens between words.

| Part          | Required  | Description                                                              |
| ------------- | --------- | ------------------------------------------------------------------------ |
| `team-`       | optional  | Your team's or organisation's short name, such as `acme-`. Skip it when working alone. |
| `domain`      | yes       | Primary technology                                                       |
| `subdomain`   | if needed | Component within the domain                                              |
| `description` | yes       | What the doc is about — conveys purpose                                  |

Use the `team-` prefix for notes about **your own** setup, decisions and architecture, so they stand
apart from general how-tos that anyone could follow.

### Examples

| Filename                      | Team   | Domain   | Subdomain | Folder       |
| ----------------------------- | ------ | -------- | --------- | ------------ |
| `aws-iam-role-create.md`      |        | aws      | iam       | `handbook/`  |
| `kafka-topic-create.md`       |        | kafka    | topic     | `handbook/`  |
| `opencode-install.md`         |        | opencode |           | `handbook/`  |
| `acme-eks-cluster-upgrade.md` | `acme` | eks      | cluster   | `handbook/`  |
| `acme-argocd-vs-flux.md`      | `acme` | argocd   |           | `decisions/` |

**Edge case:** a note about several domains (`acme-eks-to-ecs-migration.md`, in `decisions/`) uses the
primary domain in the filename and tags the other.

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

Examples. Use the domains your own notes are about.

| Domain      | Covers             | Subdomains (for filenames)       |
| ----------- | ------------------ | -------------------------------- |
| `aws`       | AWS services       | `iam`, `vpc`, `s3`               |
| `eks`       | Amazon EKS         | `cluster`, `node-group`, `irsa`  |
| `k8s`       | Generic Kubernetes | `deployments`, `ingress`, `rbac` |
| `argocd`    | ArgoCD             | `apps`, `appsets`, `sync`        |
| `helm`      | Helm               | `charts`, `repos`, `values`      |
| `terraform` | Terraform/IaC      | `modules`, `state-file`, `vars`  |
| `kafka`     | Apache Kafka       | `topics`, `consumers`, `connect` |

### Domain vs Tag Strategy

**Rule:** The filename domain reflects the note's primary focus. Use tags for referenced tools.

| Note is about...                           | Filename starts with | Tags include           |
| ------------------------------------------ | -------------------- | ---------------------- |
| General monitoring setup that uses Grafana | `monitoring-`        | `#monitoring #grafana` |
| Grafana-specific dashboard config          | `grafana-`           | `#grafana`             |
| EKS cluster using API Gateway              | `eks-`               | `#eks #apigw`          |
| Terraform module for EKS                   | `terraform-`         | `#terraform #eks`      |

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

The **type** says what kind of note it is (one per note) and matches its folder. It is for humans browsing the vault; semantic search doesn't depend on it. Teams define their own types; the table below is a suggested baseline. The **domain** is the main technology or topic, and the Domains table is only guidance, not a closed list. Tag order doesn't matter.

Use the `Tags:` line below the description for indexed tag metadata. The index stores lowercase,
unique tag names without `#`, as a list rather than a text field. YAML frontmatter is excluded
from indexing; tags written only there are not stored.

| Type           | Folder          |
| -------------- | --------------- |
| `architecture` | `architecture/` |
| `handbook`     | `handbook/`     |
| `decision`     | `decisions/`    |
| `script`       | `scripts/`      |
| `incident`     | `incidents/`    |
| `team`         | `team/`         |

## Title and Structure

- The `# Title` reflects the filename, without the "-" and with proper capitalization.
- Directly under the title: one short description paragraph, then `Links:` (optional) and `Tags:`.
  Say what the note covers before giving reading or execution instructions. No `## Summary`
  heading is needed. Keep this paragraph within 400 characters: it becomes the context string
  stored and embedded with each fragment. Context stops before `Links:` or `Tags:`.
- A `## Table of Contents` and `Links` are optional for now. A `## References` section goes last.
  Search skips References and Table of Contents, so they add no noise.

## Writing Notes

Notes vary (how-tos, decisions, user stories, plans, diagrams), so these are guidelines, not a format.

- **Say what the note is about.** The title and the short description under it are what a reader sees
  first, and search shows every passage under its note's title. Replace the template's placeholder
  text. Prefer a descriptive title over a bare ticket ID. A generic section heading such as `Verify`
  keeps both its full heading path and the note's description as context.
- **Describe images.** Search reads text only. Next to a diagram or screenshot, write a sentence on what it shows.
- **Look before writing.** If a note on the topic exists, update it instead of adding a duplicate, and
  link the related notes.
- **Never invent facts.** If you are unsure, leave a clear `TODO` for a person.
- **No secrets** in any note: no passwords, tokens or keys.

## Scripts & Runbooks

If you use Obsidian with the `execute-code` plugin, notes in `scripts/` can be **runnable** (a ▶
button on each code block). Define an operation once; anyone can run the vetted steps instead of
re-deriving commands.
Follow these rules (start from `templates/runbook-template.md`):

- **Share state through a temp file.** Shell blocks are separate processes, so a first **Setup** block writes the run's non-secret config (accounts, hosts, names) to `/tmp/<note>.env`. Each step block `source`s that file; a final **Cleanup** block removes it. If the file is gone (the OS clears `/tmp` every few days), re-run **Setup**.
- **Never store secrets** in the note or the env file. Read them at run time from the environment or a secret tool (`aws sso login`, `~/.pgpass`, OS keychain).
- **Portable paths** via magic commands (`@vault_path`, `@note_path`) — never hardcoded absolute paths.
- **PATH.** `execute-code` runs with Obsidian's launch PATH, which on macOS omits Homebrew dirs — so `aws`, `psql`, etc. may be "not found". Add Homebrew to it in the Setup block: the runbook template uses `brew shellenv`; prepending `/opt/homebrew/bin:/usr/local/bin` to `PATH` works too.
