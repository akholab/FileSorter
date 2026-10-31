#!/usr/bin/env bash
# PreToolUse hook for the reviewer subagent only (set in .claude/agents/reviewer.md).
# Allows read-only git commands, optionally piped into read-only filters.
# Not covered: textconv or external diff drivers that the repo's own git config
# sets up still run on git diff/log/show, as they would for any git user.
# Everything else is blocked with exit 2, so the reviewer can't change files.
set -u

input=$(cat)
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
elif command -v python3 >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
else
  cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' | sed 's/\\"/"/g')
fi

block() {
  echo "Blocked: the reviewer is read-only ($1)." >&2
  echo "Allowed: git diff, log, show, status, rev-parse, ls-files, merge-base, blame, symbolic-ref (read form), branch --show-current, piped only into head, tail, wc, grep or cat." >&2
  exit 2
}

[ -n "$cmd" ] || block "empty command"
case "$cmd" in
  *'>'*|*'<'*|*';'*|*'&'*|*'`'*|*'$('*|*$'\n'*|*'\n'*) block "redirects, chains, substitutions and newlines aren't allowed" ;;
  *--output*|*--ext-diff*|*--textconv*) block "git options that write files or run programs aren't allowed" ;;
esac

check_git() {
  # $@ = words of one segment, starting with "git"
  shift
  # Global options that only pick the repo or turn off the pager.
  while [ $# -gt 0 ]; do
    case "$1" in
      -C) [ $# -ge 2 ] || block "git -C without a folder"; shift 2 ;;
      --no-pager) shift ;;
      *) break ;;
    esac
  done
  [ $# -gt 0 ] || block "bare git"
  local sub=$1; shift
  case "$sub" in
    diff|log|show|status|rev-parse|ls-files|merge-base|blame) ;;
    symbolic-ref)
      local n=0 a
      for a in "$@"; do
        case "$a" in
          --short|-q|--quiet) ;;
          -*) block "git symbolic-ref $a can change or delete a ref" ;;
          *) n=$((n + 1)) ;;
        esac
      done
      [ "$n" -le 1 ] || block "git symbolic-ref with two arguments changes a ref"
      ;;
    branch)
      [ "$*" = "--show-current" ] || block "only git branch --show-current is allowed"
      ;;
    *) block "git $sub isn't on the read-only list" ;;
  esac
}

first=1
rest=$cmd
while :; do
  seg=${rest%%|*}
  read -r -a words <<<"$seg"
  [ "${#words[@]}" -gt 0 ] || block "empty pipeline step"
  if [ "$first" -eq 1 ]; then
    [ "${words[0]}" = git ] || block "${words[0]} isn't allowed; use the Read, Grep and Glob tools for files"
    check_git "${words[@]}"
    first=0
  else
    case "${words[0]}" in
      head|tail|wc|grep|cat) ;;   # not sort or uniq: they can write files
      *) block "${words[0]} isn't an allowed filter" ;;
    esac
  fi
  [ "$seg" = "$rest" ] && break
  rest=${rest#*|}
done
exit 0
