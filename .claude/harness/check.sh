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

step "syntax" syntax
step "pyflakes" lint

if [ "$fail" -eq 0 ]; then echo "check: all steps passed"; fi
exit "$fail"
