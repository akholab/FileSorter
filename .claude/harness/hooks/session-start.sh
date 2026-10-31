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

# Claude Code skips the reviewer's own hook in folders it hasn't trusted.
# guard.sh still enforces it, but ask the user rather than skip silently.
# Not in cloud sessions: each one starts in a fresh, untrusted container.
# Only on a fresh start, not on resume, clear or compact.
source=$(json_field "$input" source)
if [ "$source" = startup ] && [ "${CLAUDE_CODE_REMOTE:-}" != true ] && ! folder_trusted; then
  echo "Claude Code hasn't trusted this folder yet, so it skips hooks in agent files (the reviewer's read-only hook; guard.sh still enforces it)."
  echo "If the user is here, ask them once whether to trust it: they run \`claude\` in this folder and accept the trust prompt (takes effect next session). Don't edit ~/.claude.json yourself. In an unattended run, mention it in your final report instead."
  echo
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
