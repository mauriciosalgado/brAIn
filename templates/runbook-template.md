# {{title}}

Write one short paragraph (at most 400 characters) naming the system, operation, target environment and when to use this runbook.
This description is embedded with every chunk as shared context; replace this guidance with specific facts.

Tags: #domain #script

Run the blocks **in order** from Obsidian (the `execute-code` plugin's ▶ button).

## Prerequisites

- Tools this runbook needs (CLIs, versions).
- **Secrets** — provided at run time, never in this note: e.g. `aws sso login`, `~/.pgpass`, keychain.

## Setup — write this run's config

Replace the example config and `/tmp/my-runbook.env` path with this note's non-secret run config.

```bash
cat > /tmp/my-runbook.env << 'EOF'
eval "$(/opt/homebrew/bin/brew shellenv)"   # add Homebrew to Obsidian's minimal PATH

export EXAMPLE_HOST="localhost"
export EXAMPLE_NAME="demo"

EOF
```

## Step 1 — <action>

Describe what this action changes and the expected result.

```bash
source /tmp/my-runbook.env
echo "Doing <action> against $EXAMPLE_HOST/$EXAMPLE_NAME"
```

## Step 2 — <action>

Describe what this action changes and the expected result.

```bash
source /tmp/my-runbook.env
echo "Next step for $EXAMPLE_NAME"
```

## Validation

Describe how to check the operation succeeded, including the expected output or state.

## Cleanup — remove this run's config

```bash
rm -f /tmp/my-runbook.env
```

## References

- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)
