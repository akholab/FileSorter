#!/usr/bin/env bash
# One command that says whether the project is healthy. Exit 0 means pass.
# Written by harness setup; edit freely. Keep the whole run under ~2 minutes.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

fail=0
step() {
  local name=$1; shift
  printf '== %s\n' "$name"
  if ! "$@"; then
    printf 'FAIL: %s\n' "$name"
    fail=1
  fi
}

# Python files live at the repo root; there is no package folder.
py_files() { git ls-files --cached --others --exclude-standard '*.py'; }

# Byte-compile every file: catches syntax errors on any OS.
syntax() { py_files | xargs python3 -m py_compile; }

# Pyflakes runs on Linux, macOS and Windows without importing the code, so it
# works even though the app imports pywin32. Unused imports and variables are
# allowed for now; anything else (undefined names, bad syntax) fails.
lint() {
  if ! python3 -m pyflakes --version >/dev/null 2>&1; then
    # Fresh machines (new cloud sessions) won't have it yet.
    python3 -m pip install -q -r requirements-dev.txt >/dev/null 2>&1 ||
      python3 -m pip install -q --user -r requirements-dev.txt >/dev/null 2>&1
    if ! python3 -m pyflakes --version >/dev/null 2>&1; then
      echo "pyflakes is not installed and pip couldn't install it: run pip install -r requirements-dev.txt"
      return 1
    fi
  fi
  local out
  out=$(py_files | xargs python3 -m pyflakes 2>&1 | grep -vE "imported but unused|assigned to but never used")
  [ -z "$out" ] || { printf '%s\n' "$out"; return 1; }
}

# The owner's personal data files must stay out of git (they are git-ignored,
# but `git add -f` or an edited .gitignore could bring them back).
private_untracked() {
  local tracked
  tracked=$(git ls-files -- file_index.json file_indexer_config.ini file_undo_log.json file_learned_choices.json rules.toml)
  [ -z "$tracked" ] || { echo "Personal data files are tracked by git: $tracked. Run git rm --cached on them."; return 1; }
}

# The reviewer subagent must stay read-only: no editing tools in its tools line.
reviewer_read_only() {
  local f=.claude/agents/reviewer.md tools
  tools=$(awk '/^---$/ { n++; next } n == 1 && sub(/^tools:[[:space:]]*/, "")' "$f")
  [ -n "$tools" ] || { echo "$f: no tools line (it would inherit every tool)"; return 1; }
  if printf '%s\n' "$tools" | grep -qwE 'Edit|Write|NotebookEdit|MultiEdit'; then
    echo "$f: tools include an editing tool: $tools"; return 1
  fi
}

# Unit tests for the pure modules (categorizer.py, safemove.py: no Windows
# imports, so they run on any OS).
tests() {
  if ! python3 -m pytest --version >/dev/null 2>&1; then
    python3 -m pip install -q -r requirements-dev.txt >/dev/null 2>&1 ||
      python3 -m pip install -q --user -r requirements-dev.txt >/dev/null 2>&1
    if ! python3 -m pytest --version >/dev/null 2>&1; then
      echo "pytest is not installed and pip couldn't install it: run pip install -r requirements-dev.txt"
      return 1
    fi
  fi
  python3 -m pytest -q tests
}

step "syntax" syntax
step "private files untracked" private_untracked
step "pyflakes" lint
step "reviewer agent is read-only" reviewer_read_only
step "tests" tests

if [ "$fail" -eq 0 ]; then echo "check: all steps passed"; fi
exit "$fail"
