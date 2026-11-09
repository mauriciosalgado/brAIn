#!/usr/bin/env bash
# Checks that brAIn is installed and working on this machine.
set -euo pipefail
cd "$(dirname "$0")"

ok=true

# check "<what is checked>" "<how to fix it>" <command that succeeds when all is well>
check() {
  local what=$1 fix=$2
  shift 2
  if "$@" >/dev/null 2>&1; then
    echo "✓ $what"
  else
    echo "✗ $what ($fix)"
    ok=false
  fi
}

# Loads the model from disk only (nothing is downloaded) and embeds a sentence, so a missing,
# partial or corrupt download is caught.
model_works() {
  uv run --no-sync python -c "import sys; from rag.index import embeddings; sys.exit(not embeddings.model_works())"
}

# The branch the index follows (main, or BRAIN_BRANCH) must exist and have commits.
index_branch() {
  uv run --no-sync python -c "from rag import config, git; git.branch_tip(config.BRANCH)"
}

# Hooks only run when git is pointed at .githooks and the scripts are executable.
hooks_enabled() {
  [ "$(git config --get core.hooksPath)" = .githooks ] || return 1
  [ -x .githooks/reference-transaction ]
}

check "git 2.42+ installed" "https://git-scm.com/; run from a Git clone" git cat-file --batch -Z </dev/null
check "uv installed" "https://docs.astral.sh/uv/getting-started/installation/" command -v uv
check "dependencies match uv.lock" "run ./setup.sh" uv sync --check
check "brain.toml is valid" "run: uv run rag status, and fix what it says" uv run --no-sync python -c "import rag.config"
check "MCP server loads" "run ./setup.sh" uv run --no-sync python -c "import rag.mcp.server"
check "embedding model works offline" "run ./setup.sh; needs internet once" model_works
check "git hooks enabled" "run ./setup.sh" hooks_enabled
check "index branch found" "create 'main', or set branch in brain.toml to the branch your notes are on" index_branch
check "index up to date" "run ./setup.sh; details: uv run rag status" uv run --no-sync rag status

if [ "$ok" = false ]; then
  echo
  echo "Fix the issues above, then re-run ./doctor.sh"
  exit 1
fi

echo
echo "All good ✔"
