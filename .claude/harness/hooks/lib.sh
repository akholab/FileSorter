#!/usr/bin/env bash
# Shared helpers for the harness hooks. Sourced, not run.

HARNESS_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HARNESS_DIR="$HARNESS_ROOT/.claude/harness"
HARNESS_STATE="$HARNESS_DIR/.state"

# True while setup hasn't finished. HARNESS_IGNORE_SETUP=1 lets setup test the
# hooks for real before it deletes SETUP.md.
setup_pending() {
  [ -f "$HARNESS_DIR/SETUP.md" ] && [ -z "${HARNESS_IGNORE_SETUP:-}" ]
}

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

# True unless we can see that Claude Code hasn't trusted this folder (or a
# parent of it) in ~/.claude.json. Anything unclear (no config, no python3, a
# malformed file, a crash) counts as trusted, so there are no false alarms.
folder_trusted() {
  [ -f "$HOME/.claude.json" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 -c '
import json, os, sys
try:
    projects = json.load(open(sys.argv[1])).get("projects", {})
    if not isinstance(projects, dict):
        sys.exit(0)
    def trusted(p):
        e = projects.get(p)
        return isinstance(e, dict) and e.get("hasTrustDialogAccepted") is True
    for start in {os.path.abspath(sys.argv[2]), os.path.realpath(sys.argv[2])}:
        p = start
        while True:
            if trusted(p):
                sys.exit(0)
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
except Exception:
    sys.exit(0)
sys.exit(3)
' "$HOME/.claude.json" "$HARNESS_ROOT" </dev/null >/dev/null 2>&1
  [ $? -ne 3 ]
}
