#!/usr/bin/env bash
# Sets up brAIn on this machine: dependencies, git hooks and the first index. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "✗ missing: $1 ($2)"; exit 1; }; }
need git "https://git-scm.com/"
need uv "https://docs.astral.sh/uv/getting-started/installation/"

if ! git cat-file --batch -Z </dev/null >/dev/null 2>&1; then
  echo "✗ Git 2.42+ and a Git clone are required (https://git-scm.com/)"
  exit 1
fi

echo "→ Installing dependencies"
uv sync

echo "→ Enabling git hooks (notes are synced whenever local branches change)"
chmod +x .githooks/*
hooks=$(git config --get core.hooksPath || true)
if [ -n "$hooks" ] && [ "$hooks" != .githooks ]; then
  echo "  Replacing core.hooksPath '$hooks' with required .githooks; other hooks will no longer run."
fi
git config --local core.hooksPath .githooks

echo "→ Embedding model (downloaded if missing or damaged, about 320 MB, needs internet once)"
uv run rag model

echo "→ Indexing notes"
uv run rag sync

echo "→ Checking the installation"
./doctor.sh
