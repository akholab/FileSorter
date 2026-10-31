# Progress

Agents: read this at the start of a session and update it before you stop. Keep it short; old log lines can be trimmed to the last 20.

## Goal

An intelligent file sorter that runs on all of the owner's devices, not just Windows. It started as a Windows-only app.

## Done means

`.claude/harness/check.sh` passes and the change is described in this file.

## Tasks

- [ ] Make Windows-only code optional: guard the `win32api`/`win32gui` imports and `os.startfile`, and make `pywin32` a Windows-only requirement, so the app starts on macOS and Linux.
- [ ] Use per-OS defaults for watch folders, file paths and launchers (the `.bat`/`.vbs` files only work on Windows).
- [ ] Split the categorizing logic away from the GUI and add a small pytest suite for it, then add `pytest` to `check.sh`.

## Session log

<!-- Newest first. One line per session: date, what changed, what's next or blocked. -->
- 2026-10-31: Harness installed. Fixed two bugs pyflakes found (missing `import platform`, lambda using `e` after its except block). Untracked the runtime data files.
