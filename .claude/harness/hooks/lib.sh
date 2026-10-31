#!/usr/bin/env bash
# Shared helpers for the harness hooks. Sourced, not run.

HARNESS_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HARNESS_DIR="$HARNESS_ROOT/.claude/harness"
HARNESS_STATE="$HARNESS_DIR/.state"

# Pull a string field out of the hook's JSON input without needing jq.
json_field() {
  printf '%s' "$1" | sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
}

# Keep session ids safe to use in a file name.
safe_id() {
  printf '%s' "${1:-unknown}" | tr -c 'A-Za-z0-9_-' '_'
}

# A fingerprint of the working tree: HEAD, staged and unstaged changes, and
# untracked files. Empty when the project isn't a git repo.
tree_fingerprint() {
  (
    cd "$HARNESS_ROOT" || exit 0
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
    {
      git rev-parse HEAD 2>/dev/null
      git diff HEAD 2>/dev/null
      git ls-files --others --exclude-standard -z -- . ':!.claude/harness/.state' 2>/dev/null |
        while IFS= read -r -d '' f; do
          printf '%s\n' "$f"
          cat -- "$f" 2>/dev/null
        done
    } | cksum | cut -d ' ' -f 1
  )
}
