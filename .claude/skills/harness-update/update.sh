#!/usr/bin/env bash
# Merge a newer harness kit into this project (Q34-Q37 in MyClaudeSettings harness/README.md).
# Usage, from the project root:
#   update.sh <MyClaudeSettings checkout> <base commit> <new commit> <report dir>
# <base> is the kit commit the project was installed or last updated from.
# For each kit-owned file it does a three-way merge (project edits kept, conflicts
# left as markers), then writes into <report dir>:
#   report.txt     one line per change: ADDED, UPDATED, CONFLICT, KEPT-DELETED (project removed
#                  something the kit changed), EXISTS-DIFFERS (project has its own file where the
#                  kit adds one), REMOVED-UPSTREAM, HOOK-ADD
# Run the copy in the MyClaudeSettings checkout, not the project's: this script may update itself.
#   feedback.diff  project edits to kit-owned files since <base> (candidates for kit feedback)
#   check.diff     changes to the kit's check.sh template (suggest, never apply)
# It never touches check.sh, progress.md, research.md or permission rules.
# Bash 3.2 compatible (macOS). Needs git, diff, awk.
set -uo pipefail

[ $# -eq 4 ] || { echo "usage: $0 <MyClaudeSettings dir> <base> <new> <report dir>" >&2; exit 64; }
MCS=$1; BASE=$2; NEW=$3; OUT=$4
KIT=harness/kit/.claude
for ref in "$BASE" "$NEW"; do
  git -C "$MCS" cat-file -e "$ref^{commit}" 2>/dev/null || { echo "commit $ref not found in $MCS (shallow clone? fetch more history)" >&2; exit 65; }
done
[ -d .claude/harness ] || { echo "run from the project root (no .claude/harness here)" >&2; exit 66; }

mkdir -p "$OUT"
: >"$OUT/report.txt"; : >"$OUT/feedback.diff"; : >"$OUT/check.diff"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/harness-update.XXXXXX") || exit 70

# show <ref> <path in MyClaudeSettings> <dest>: returns 1 if the path doesn't exist at ref.
show() { git -C "$MCS" show "$1:$2" >"$3" 2>/dev/null; }
note() { printf '%s %s\n' "$1" "$2" >>"$OUT/report.txt"; }
feedback() { # feedback <label> <old file> <project file> <new file>
  # Skip when the project already matches the new kit (its "edits" came from the kit).
  if ! cmp -s "$2" "$3" && ! cmp -s "$3" "$4"; then
    { printf '### %s\n' "$1"; diff -u --label "kit $BASE" --label "project" "$2" "$3"; printf '\n'; } >>"$OUT/feedback.diff"
  fi
}

# merge_into <label> <project file> <old> <new>: three-way merge, result written to <project file>.
merge_into() {
  local label=$1 proj=$2 old=$3 new=$4
  if cmp -s "$old" "$new" || cmp -s "$proj" "$new"; then return 0; fi
  cp "$proj" "$TMP/merged"
  if git merge-file -L project -L "kit $BASE" -L "kit $NEW" "$TMP/merged" "$old" "$new"; then
    cp "$TMP/merged" "$proj"; note UPDATED "$label"
  else
    case $proj in
      # A live hook with conflict markers fails with exit 2, which blocks: keep the project's
      # version running and put the merge next to it.
      *.sh) cp "$TMP/merged" "$proj.merge"; note CONFLICT "$label (see $proj.merge)" ;;
      *) cp "$TMP/merged" "$proj"; note CONFLICT "$label" ;;
    esac
  fi
}

# --- 1. Whole kit-owned files. The installer (rules/, SETUP.md, templates/) is skipped.
{ git -C "$MCS" ls-tree -r --name-only "$BASE" -- "$KIT"; git -C "$MCS" ls-tree -r --name-only "$NEW" -- "$KIT"; } |
  sort -u | grep -vE "^$KIT/(rules/|harness/SETUP\.md$|harness/templates/)" >"$TMP/files"

while IFS= read -r src; do
  rel=${src#harness/kit/}
  has_old=0; has_new=0
  show "$BASE" "$src" "$TMP/old" && has_old=1
  show "$NEW" "$src" "$TMP/new" && has_new=1
  if [ ! -e "$rel" ]; then
    if [ $has_old -eq 0 ] && [ $has_new -eq 1 ]; then
      mkdir -p "$(dirname "$rel")"; cp "$TMP/new" "$rel"; note ADDED "$rel"
    elif [ $has_old -eq 1 ] && [ $has_new -eq 1 ] && ! cmp -s "$TMP/old" "$TMP/new"; then
      note KEPT-DELETED "$rel"
    fi
  elif [ $has_new -eq 0 ]; then
    note REMOVED-UPSTREAM "$rel"
  elif [ $has_old -eq 0 ]; then
    # Project has its own file where the new kit adds one: no base to merge from, so keep the
    # project's file, report it, and list the difference.
    if ! cmp -s "$rel" "$TMP/new"; then
      note EXISTS-DIFFERS "$rel"
      { printf '### %s (no base; project vs new kit)\n' "$rel"; diff -u --label "kit $NEW" --label "project" "$TMP/new" "$rel"; printf '\n'; } >>"$OUT/feedback.diff"
    fi
  else
    feedback "$rel" "$TMP/old" "$rel" "$TMP/new"
    merge_into "$rel" "$rel" "$TMP/old" "$TMP/new"
  fi
  case $rel in *.sh) [ -e "$rel" ] && chmod +x "$rel" ;; esac
done <"$TMP/files"

# --- 2. The kit's sections of AGENTS.md, one at a time.
# section <file> <heading>: print the heading line through the line before the next "## ".
section() { awk -v h="$2" '$0 == h { on = 1; print; next } on && /^## / { exit } on' "$1"; }
has_heading() { grep -qxF "$2" "$1"; }
# splice <file> <heading> <body file>: replace that section with the body file.
splice() {
  awk -v h="$2" -v body="$3" '
    $0 == h { while ((getline l < body) > 0) print l; skip = 1; next }
    skip && /^## / { skip = 0 }
    !skip' "$1" >"$1.tmp" && mv "$1.tmp" "$1"
}
# insert_section <file> <heading before it in the template> <heading after it> <body file>:
# add a new section after the first, else before the second, else at the end.
insert_section() {
  if [ -n "$2" ] && has_heading "$1" "$2"; then
    awk -v h="$2" -v body="$4" '
      $0 == h { on = 1; print; next }
      on && /^## / { while ((getline l < body) > 0) print l; on = 0 }
      { print }
      END { if (on) while ((getline l < body) > 0) print l }' "$1" >"$1.tmp" && mv "$1.tmp" "$1"
  elif [ -n "$3" ] && has_heading "$1" "$3"; then
    awk -v h="$3" -v body="$4" '
      $0 == h { while ((getline l < body) > 0) print l }
      { print }' "$1" >"$1.tmp" && mv "$1.tmp" "$1"
  else
    { printf '\n'; cat "$4"; } >>"$1"
  fi
}
# next_heading <file> <heading>: the "## " heading that follows it.
next_heading() { awk -v h="$2" 'on && /^## / { print; exit } $0 == h { on = 1 }' "$1"; }

if [ -f AGENTS.md ] && show "$NEW" "$KIT/harness/templates/AGENTS.md" "$TMP/agents-new"; then
  show "$BASE" "$KIT/harness/templates/AGENTS.md" "$TMP/agents-old" || : >"$TMP/agents-old"
  prev=""
  for h in "## Working on a task" "## Writing code" "## Model and effort"; do
    label="AGENTS.md: $h"
    if ! has_heading "$TMP/agents-new" "$h"; then prev=$h; continue; fi
    section "$TMP/agents-new" "$h" >"$TMP/sec-new"
    if has_heading "$TMP/agents-old" "$h"; then section "$TMP/agents-old" "$h" >"$TMP/sec-old"; else : >"$TMP/sec-old"; fi
    if has_heading AGENTS.md "$h"; then
      section AGENTS.md "$h" >"$TMP/sec-proj"
      [ -s "$TMP/sec-old" ] && feedback "$label" "$TMP/sec-old" "$TMP/sec-proj" "$TMP/sec-new"
      [ -s "$TMP/sec-old" ] || cp "$TMP/sec-proj" "$TMP/sec-old"
      before=$(cat "$OUT/report.txt")
      merge_into "$label" "$TMP/sec-proj" "$TMP/sec-old" "$TMP/sec-new"
      [ "$before" = "$(cat "$OUT/report.txt")" ] || splice AGENTS.md "$h" "$TMP/sec-proj"
    elif [ -s "$TMP/sec-old" ]; then
      cmp -s "$TMP/sec-old" "$TMP/sec-new" || note KEPT-DELETED "$label"
    else
      insert_section AGENTS.md "$prev" "$(next_heading "$TMP/agents-new" "$h")" "$TMP/sec-new"; note ADDED "$label"
    fi
    prev=$h
  done
fi

# --- 3. Hook entries in settings.json: report which to add; Claude edits the JSON.
hooks_in() { grep -oE 'harness/hooks/[A-Za-z0-9_.-]+\.sh' "$1" 2>/dev/null | sort -u; }
if show "$NEW" "$KIT/harness/templates/settings.template.json" "$TMP/set-new"; then
  show "$BASE" "$KIT/harness/templates/settings.template.json" "$TMP/set-old" || : >"$TMP/set-old"
  for hook in $(hooks_in "$TMP/set-new"); do
    if hooks_in .claude/settings.json | grep -qxF "$hook"; then continue; fi
    # A hook the old kit had and the project lacks was removed on purpose: leave it out.
    hooks_in "$TMP/set-old" | grep -qxF "$hook" || note HOOK-ADD "settings.json hook $hook"
  done
fi

# --- 4. check.sh template changes: suggestions only.
if show "$BASE" "$KIT/harness/templates/check.sh" "$TMP/chk-old" && show "$NEW" "$KIT/harness/templates/check.sh" "$TMP/chk-new"; then
  diff -u --label "kit $BASE" --label "kit $NEW" "$TMP/chk-old" "$TMP/chk-new" >"$OUT/check.diff"
fi

# shortcut: leaves a few small files in $TMP when killed mid-run; they're in the OS temp folder.
rm -f "$TMP"/* && rmdir "$TMP"
echo "report: $OUT/report.txt"
cat "$OUT/report.txt"
grep -q '^CONFLICT ' "$OUT/report.txt" && exit 3
exit 0
