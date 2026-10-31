#!/usr/bin/env bash
# PreToolUse hook for Bash: block the commands that can destroy work, even
# when they're wrapped (sudo, bash -c '...', /bin/rm, git -C dir ...).
# Exit 2 blocks the call and shows Claude the reason.
set -u

input=$(cat)

# Get tool_input.command. Prefer a real JSON parser; fall back to sed.
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
elif command -v python3 >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
else
  cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' | sed 's/\\"/"/g')
fi
[ -n "$cmd" ] || exit 0

block() {
  echo "Blocked by the harness guard: $1." >&2
  echo "Use a safer command. If this really is needed, explain why and ask the user to run it themselves." >&2
  exit 2
}

# Split into simple commands on shell separators and quotes, so that
# `cd x && rm -rf y` and `bash -c 'rm -rf y'` are both seen as `rm -rf y`.
segments=$(printf '%s\n' "$cmd" | tr ';&|()`"'"'"'' '\n\n\n\n\n\n\n')

# Leading words that run the next word as the command.
strip_wrappers() {
  local -a w=("$@")
  local i=0
  while [ "$i" -lt "${#w[@]}" ]; do
    case "${w[$i]}" in
      sudo|doas|command|builtin|exec|nohup|time|nice|env|xargs|stdbuf|noglob) i=$((i + 1)) ;;
      timeout) i=$((i + 2)) ;;
      -*|*=*) i=$((i + 1)) ;;   # flags of the wrappers above, VAR=value
      *) break ;;
    esac
  done
  printf '%s\n' "${w[@]:$i}"
}

# Build and cache folders that are always safe to delete recursively.
safe_rm_target() {
  local t=${1%/}
  t=${t#./}
  case "$t" in
    ""|"."|".."|"/"|"~"|"*"|.*/*..*|*..*) return 1 ;;
  esac
  case "$t" in
    /tmp/?*|/var/tmp/?*) return 0 ;;
  esac
  local base=${t##*/}
  case "$base" in
    node_modules|dist|build|out|target|coverage|.cache|__pycache__|.pytest_cache|.mypy_cache|.ruff_cache|.venv|venv|.next|.nuxt|.turbo|.parcel-cache|tmp|.tmp) ;;
    *) return 1 ;;
  esac
  # Relative paths only, apart from /tmp above.
  case "$t" in /*|~*) return 1 ;; esac
  return 0
}

check_rm() {
  local recursive=0 a
  local -a targets=()
  for a in "$@"; do
    case "$a" in
      --recursive) recursive=1 ;;
      --*) ;;
      -*) case "$a" in *r*|*R*) recursive=1 ;; esac ;;
      *) targets+=("$a") ;;
    esac
  done
  [ "$recursive" -eq 1 ] || return 0
  # A quoted or computed target ("$DIR", "my folder") lands in another segment,
  # so the guard can't see it: refuse rather than guess.
  [ "${#targets[@]}" -gt 0 ] || block "recursive delete of a target the guard can't read (quoted or computed path)"
  for a in "${targets[@]}"; do
    safe_rm_target "$a" || block "recursive delete of '$a' (only build and cache folders like node_modules, dist or __pycache__ may be deleted recursively)"
  done
}

check_git() {
  # Skip global options to find the subcommand: git -C dir -c k=v --no-pager push ...
  local -a a=("$@")
  local i=0
  while [ "$i" -lt "${#a[@]}" ]; do
    case "${a[$i]}" in
      -C|-c|--git-dir|--work-tree|--namespace) i=$((i + 2)) ;;
      -*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  local sub=${a[$i]:-}
  local -a rest=("${a[@]:$((i + 1))}")
  local r
  case "$sub" in
    push)
      for r in "${rest[@]}"; do
        case "$r" in
          --force|--force-with-lease|--force-with-lease=*|--force-if-includes|--mirror) block "force-push ($r)" ;;
          --delete) block "deleting a remote branch (git push --delete)" ;;
          --*) ;;
          -*) case "$r" in *f*) block "force-push ($r)" ;; *d*) block "deleting a remote branch (git push $r)" ;; esac ;;
          +*) block "force-push (refspec $r)" ;;
          :*) block "deleting a remote branch (refspec $r)" ;;
        esac
      done ;;
    reset)
      for r in "${rest[@]}"; do [ "$r" = "--hard" ] && block "git reset --hard (throws away uncommitted work)"; done ;;
    clean)
      for r in "${rest[@]}"; do
        case "$r" in
          --force) block "git clean --force (deletes untracked files)" ;;
          --*) ;;
          -*) case "$r" in *f*) block "git clean $r (deletes untracked files)" ;; esac ;;
        esac
      done ;;
    branch)
      local del=0 force=0
      for r in "${rest[@]}"; do
        case "$r" in
          -D) block "deleting a branch with git branch -D" ;;
          --delete|-d) del=1 ;;
          --force|-f) force=1 ;;
        esac
      done
      [ "$del" -eq 1 ] && [ "$force" -eq 1 ] && block "force-deleting a branch" ;;
  esac
  return 0
}

while IFS= read -r seg; do
  # shellcheck disable=SC2086
  set -f; set -- $seg; set +f
  [ "$#" -gt 0 ] || continue
  words=()   # no mapfile: macOS ships bash 3.2
  while IFS= read -r w; do words+=("$w"); done < <(strip_wrappers "$@")
  [ "${#words[@]}" -gt 0 ] || continue
  prog=${words[0]##*/}   # /bin/rm -> rm
  case "$prog" in
    rm) check_rm "${words[@]:1}" ;;
    git) check_git "${words[@]:1}" ;;
  esac
done <<< "$segments"

exit 0
