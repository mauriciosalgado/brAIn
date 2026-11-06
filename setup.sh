#!/usr/bin/env bash
# Sets up brAIn on this machine: dependencies, git hooks and the first index. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "✗ missing: $1 ($2)"; exit 1; }; }
need git "https://git-scm.com/"
need uv "https://docs.astral.sh/uv/getting-started/installation/"

echo "→ Installing dependencies"
uv sync

echo "→ Enabling git hooks (notes are synced after a pull, merge or rebase)"
chmod +x .githooks/*
hooks=$(git config --local core.hooksPath || true)
if [ -z "$hooks" ] || [ "$hooks" = .githooks ]; then
  git config --local core.hooksPath .githooks
else
  echo "  core.hooksPath is '$hooks', so it was left alone."
  echo "  To get automatic updates, call .githooks/sync-notes from your own hooks."
fi

echo "→ Embedding model (downloaded if missing or damaged, about 320 MB, needs internet once)"
uv run rag model

echo "→ Indexing notes"
uv run rag sync

echo "→ Checking the installation"
./doctor.sh
