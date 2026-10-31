# Progress

Agents: read this at the start of a session and update it before you stop. Keep it short; old log lines can be trimmed to the last 20.

## Goal

An intelligent file sorter that runs on all of the owner's devices, not just Windows. It started as a Windows-only app.

## Done means

`.claude/harness/check.sh` passes, the `reviewer` subagent's findings are fixed or answered, and the change is described in this file.

## Tasks

- [x] Run /retro once after the first working session, to turn real mistakes into checks and rules.
- [ ] Make Windows-only code optional: guard the `win32api`/`win32gui` imports and `os.startfile`, and make `pywin32` a Windows-only requirement, so the app starts on macOS and Linux.
- [ ] Use per-OS defaults for watch folders, file paths and launchers (the `.bat`/`.vbs` files only work on Windows).
- [ ] Split the categorizing logic away from the GUI and add a small pytest suite for it, then add `pytest` to `check.sh`.

## Session log

<!-- Newest first. One line per session: date, what changed, what's next or blocked. -->
- 2026-10-31: Synced kit PR #6: reviewer's Bash is read-only (reviewer-bash.sh via its frontmatter hook and guard.sh), session start asks to trust an untrusted folder.
- 2026-10-31: retro: Known mistake about testing data-file checks on the real files; AGENTS.md says how to run reviewer and /retro when not available by name; kit items sent to the kit thread.
- 2026-10-31: Harness updated to the latest kit: read-only `reviewer` subagent (`.claude/agents/reviewer.md`) and a review step before done. Review fixes: one definition of done, progress updated before review, check enforces a read-only reviewer.
- 2026-10-31: retro: ask rules for py/venv python.exe and the .bat/.vbs launchers; check fails if personal data files are tracked; AGENTS notes default branch is master.
- 2026-10-31: Harness installed (kit v2: guard hook, ask/deny permission rules, /retro skill).
- 2026-10-31: Harness installed (kit v1). Fixed two bugs pyflakes found (missing `import platform`, lambda using `e` after its except block). Untracked the runtime data files.
