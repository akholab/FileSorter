#!/usr/bin/env bash
# Stop hook: don't let Claude call a task done while check fails.
# Blocks at most MAX_BLOCKS times per session, then lets Claude stop and
# warns the user, so a test Claude can't fix doesn't loop forever.
set -u
. "$(dirname "$0")/lib.sh"

MAX_BLOCKS=3
CHECK="$HARNESS_DIR/check.sh"

input=$(cat)
session=$(safe_id "$(json_field "$input" session_id)")

# Nothing to enforce yet: no check script, or setup still running.
[ -x "$CHECK" ] || exit 0
setup_pending && exit 0

mkdir -p "$HARNESS_STATE"
fp=$(tree_fingerprint)
if [ -n "$fp" ]; then
  # Skip when this session changed nothing, or nothing changed since the last pass.
  [ "$fp" = "$(cat "$HARNESS_STATE/start-$session" 2>/dev/null)" ] && exit 0
  [ "$fp" = "$(cat "$HARNESS_STATE/last-pass" 2>/dev/null)" ] && exit 0
fi

output=$(cd "$HARNESS_ROOT" && "$CHECK" 2>&1)
status=$?

blocks_file="$HARNESS_STATE/blocks-$session"
if [ "$status" -eq 0 ]; then
  [ -n "$fp" ] && printf '%s\n' "$fp" > "$HARNESS_STATE/last-pass"
  rm -f "$blocks_file"
  exit 0
fi

blocks=$(cat "$blocks_file" 2>/dev/null || echo 0)
blocks=$((blocks + 1))
printf '%s\n' "$blocks" > "$blocks_file"

if [ "$blocks" -gt "$MAX_BLOCKS" ]; then
  printf '{"systemMessage":"Harness: check.sh is still failing after %s fix attempts. Claude was asked to tell you why."}\n' "$MAX_BLOCKS"
  exit 0
fi

{
  echo ".claude/harness/check.sh failed (attempt $blocks of $MAX_BLOCKS). Fix the cause, then finish."
  if [ "$blocks" -eq "$MAX_BLOCKS" ]; then
    echo "This is the last automatic retry. If you can't fix it, stop and tell the user plainly that check is failing, which step, and why."
  fi
  echo
  echo "Last 60 lines of output:"
  printf '%s\n' "$output" | tail -n 60
} >&2
exit 2
