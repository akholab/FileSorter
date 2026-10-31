# AGENTS.md

<!-- A map for coding agents. Keep it under ~100 lines. Only facts that can't be worked out from the code. -->

## What this is

Smart File Indexer: a personal Python desktop app (Tkinter GUI plus a system-tray mode) that watches folders such as the Desktop and suggests where to move each file by category. It was built for Windows first; the goal is to make it work on all of the owner's devices (Windows, macOS, Linux).

## Commands

| Task | Command |
|---|---|
| Install | `pip install -r requirements.txt` (app), `pip install -r requirements-dev.txt` (check tools) |
| Run | `python launcher.py` (or `python file_indexer.py` for the GUI, `python tray_indexer.py` for tray mode) |
| Test | None yet |
| Lint | pyflakes, run by `check` (it ignores unused imports and variables, so don't chase those) |
| **Check everything** | `.claude/harness/check.sh` |

Run `.claude/harness/check.sh` before you say a task is done. A Stop hook runs it too and sends you back if it fails.

The check script and hooks are bash. On Windows they need Git Bash (or WSL).

The app itself only runs on Windows today: `file_indexer.py` imports `win32api`/`win32gui` at the top, so importing it on Linux or macOS fails. That is why `check` uses byte-compiling and pyflakes, which never import the code.

## Where things live

- All Python modules are at the repo root (no package folder): `launcher.py` (entry point), `file_indexer.py` (core logic and GUI), `tray_indexer.py`, `file_monitor.py` (watchdog wrapper).
- `*.bat`, `FileManager.vbs`: Windows launchers and installers.
- `file_index.json`, `file_indexer_config.ini`: created at runtime in the working directory. Git-ignored.

## Boundaries

**Never touch:**
- `file_index.json`, `file_indexer_config.ini`: the owner's real runtime data with personal file paths. Don't read them into commits, docs or tests, and don't re-add them to git.

**Ask the user first:**
- Deploys, deleting data, force-push, publishing packages
- Running the app against real folders, or anything that moves or deletes real files
- Changing the category rules in `FileIndexer.categories`
- Editing the `.bat` / `.vbs` launchers

## Known mistakes

<!-- One line per real mistake an agent made here, and what to do instead. Add a line each time a new mistake happens. -->
- None recorded yet.

## Working on a task

1. Read `.claude/harness/progress.md` to see the goal, open tasks, and the last session's notes.
2. Work on one task at a time.
3. Done means: `.claude/harness/check.sh` passes and the change is described in `progress.md`.
4. Before you stop, update `progress.md`: tick finished tasks and add one line to the session log.

## More docs

- `README.md`: features, launch options, how to add categories.
