# Script Demo

A runnable demo of the `execute-code` plugin and our runbook conventions: fixing the PATH,
sharing state across steps, and cleaning up after. Click ▶ on each block, in order — the last
block removes everything the demo created.

Tags: #script #demo

## Prerequisites

- `jq` installed with Homebrew: `brew install jq`

## Step 1 — Setup

Obsidian launches with a minimal PATH, so Homebrew tools aren't found by default. This block adds
the Homebrew directories, confirms it worked by running `brew`, and writes the run's config to a
file that later steps read.

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

brew --version | head -1

mkdir -p "@vault_path/notes/scripts/env"
cat > "@vault_path/notes/scripts/env/script-demo.env" << 'EOF'
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export DATA_FILE="@vault_path/notes/scripts/env/script-demo.json"
EOF
```

## Step 2 — Build some data

A fresh process: it sources the config from Step 1, then uses `jq` to write a small JSON file.

```bash
source "@vault_path/notes/scripts/env/script-demo.env"

jq -n '{project: "brAIn", note_types: ["architecture", "handbook", "decisions"]}' > "$DATA_FILE"
cat "$DATA_FILE"
```

## Step 3 — Query the data

Another fresh process — proof the state came from the file, not memory. Sources the same config
and queries the JSON that Step 2 created.

```bash
source "@vault_path/notes/scripts/env/script-demo.env"

count=$(jq '.note_types | length' "$DATA_FILE")
echo "$(jq -r .project "$DATA_FILE") has $count note types:"
jq -r '.note_types[]' "$DATA_FILE"
```

## Step 4 — Cleanup

Removes the data and config files, leaving nothing behind.

```bash
source "@vault_path/notes/scripts/env/script-demo.env"

rm -f "$DATA_FILE" "@vault_path/notes/scripts/env/script-demo.env"
echo "Cleaned up."
```
## References

- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)
