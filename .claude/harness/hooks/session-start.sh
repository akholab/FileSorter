#!/usr/bin/env bash
# SessionStart hook: show Claude where the work stands, and remember the
# starting state so the Stop hook can tell whether this session changed anything.
set -u
. "$(dirname "$0")/lib.sh"

input=$(cat)
session=$(safe_id "$(json_field "$input" session_id)")

mkdir -p "$HARNESS_STATE"
tree_fingerprint > "$HARNESS_STATE/start-$session"

if setup_pending; then
  echo "Harness setup is pending in this project (.claude/harness/SETUP.md)."
  exit 0
fi

progress="$HARNESS_DIR/progress.md"
if [ -f "$progress" ]; then
  echo "Harness progress file (.claude/harness/progress.md), first 60 lines:"
  echo
  head -n 60 "$progress"
  echo
  echo "Done means .claude/harness/check.sh passes. Update progress.md before you stop."
fi
exit 0
