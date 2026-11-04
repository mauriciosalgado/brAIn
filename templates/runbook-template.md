# {{title}}

One-line purpose of this runbook. Run the blocks **in order** from Obsidian (the `execute-code`
plugin's ▶ button).

Links:
Tags: #domain #script

---

## Table of Contents

<!-- toc -->
<!-- tocstop -->

---

## Prerequisites

- Tools this runbook needs (CLIs, versions).
- **Secrets** — provided at run time, never in this note: e.g. `aws sso login`, `~/.pgpass`, keychain.

## Setup — write this run's config

```bash
cat > /tmp/my-runbook.env << 'EOF'
eval "$(/opt/homebrew/bin/brew shellenv)"   # add Homebrew to Obsidian's minimal PATH

export EXAMPLE_HOST="localhost"
export EXAMPLE_NAME="demo"

EOF
```

## Step 1 — <action>

```bash
source /tmp/my-runbook.env
echo "Doing <action> against $EXAMPLE_HOST/$EXAMPLE_NAME"
```

## Step 2 — <action>

```bash
source /tmp/my-runbook.env
echo "Next step for $EXAMPLE_NAME"
```

## Cleanup — remove this run's config

```bash
rm -f /tmp/my-runbook.env
```

---

## References

- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)

---
