# AGENTS.md

<!-- A map for coding agents. Keep it near 100 lines. Only what an agent can't see in the code or config. -->

Smart File Indexer: a personal Python desktop app (Tkinter GUI plus a system-tray mode) that watches folders such as the Desktop and suggests where to move each file by category. It was built for Windows first; the goal is to make it work on all of the owner's devices (Windows, macOS, Linux).

## Working on a task

1. Read `.claude/harness/progress.md` for the goal, open tasks and the last session's notes.
2. Work on one task at a time.
3. Update `progress.md`: tick finished tasks and add one line to the session log.
4. Run `.claude/harness/check.sh`. A Stop hook runs it too and sends you back if it fails.
5. On a change to code, config or the harness, ask the `reviewer` subagent to review the branch. Fix the findings you agree are real, re-run `check`, and list the ones you skip with a reason. One review per task.

If `reviewer` or `/retro` isn't available by name (for example in a cloud session that didn't start in this repo), start a general agent and give it `.claude/agents/reviewer.md` or `.claude/skills/retro/SKILL.md` as its instructions. The reviewer's read-only hook doesn't apply to a general agent, so tell it to change nothing.

Done means: `check` passes, the reviewer's findings are fixed or answered, and the change is described in `progress.md`.

## Writing code

<!-- Adapted from DietrichGebert/ponytail (MIT, © 2026 DietrichGebert). -->
- Make the smallest change that fully solves the task. Take the first that works: skip what nobody asked for (name it in one line), reuse code already in this repo, the standard library, an installed dependency, then new code. No new dependency for a few lines; no abstraction, option or config nobody asked for.
- Finish every part the change breaks: callers, tests, fixtures, config. For a bug, grep every caller first and fix the root cause once in the shared code.
- Never cut: validation of outside input, error handling that prevents data loss, security, accessibility, or anything the user asked for.
- A shortcut with a known limit gets a comment: `shortcut: <the limit>, <when to upgrade>`.
- When you report a finished task to the user, end with one line: what you skipped or didn't check, and any risk. Subagents with their own output format (like `reviewer`) skip this.

## Commands

| Task | Command |
|---|---|
| Install | `pip install -r requirements.txt` (app), `pip install -r requirements-dev.txt` (check tools) |
| Run | `python launcher.py` (or `python file_indexer.py` for the GUI, `python tray_indexer.py` for tray mode) |
| Test | `python3 -m pytest -q` (covers `categorizer.py`; `check` runs it) |
| Lint | pyflakes, run by `check` (it ignores unused imports and variables, so don't chase those) |
| **Check everything** | `.claude/harness/check.sh` |

The check script and hooks are bash. On Windows they need Git Bash (or WSL).

The app itself only runs on Windows today: `file_indexer.py` imports `win32api`/`win32gui` at the top, so importing it on Linux or macOS fails. That is why `check` uses byte-compiling and pyflakes, which never import the code, and why most tests only import the pure modules. `tests/test_indexer_integration.py` does import `file_indexer.py`, with tkinter, psutil and win32 stubbed out, and runs in a temp folder.

## Where to look

- All Python modules are at the repo root (no package folder): `launcher.py` (entry point), `categorizer.py` (pure sorting logic and the default categories) `safemove.py` (no-overwrite moves, the on-disk undo log, Trash) `filewatch.py` (is a file still being written?) and `learning.py` (remembers where you usually put each kind of file); none has Windows imports and all are tested in `tests/`, `file_indexer.py` (indexer and GUI), `tray_indexer.py`, `file_monitor.py` (watchdog wrapper).
- `*.bat`, `FileManager.vbs`: Windows-only launchers and installers.
- `file_index.json`, `file_indexer_config.ini`, `file_undo_log.json`, `file_learned_choices.json`: created at runtime in the working directory. Git-ignored.
- `README.md`: features, launch options, how to add categories.
- `.claude/harness/`: check, progress file and hooks (see its `README.md`). `.claude/agents/reviewer.md`: the read-only reviewer for step 5. `.claude/skills/retro/`: `/retro`.
- The default branch is `master`, not `main`: branch from and open PRs against `master`.

## Boundaries

- **Never read or edit:** `file_index.json`, `file_indexer_config.ini`, `file_undo_log.json`, `file_learned_choices.json` (the owner's real data with personal file paths; never put their contents in commits, docs or tests). Enforced by deny rules in `.claude/settings.json`.
- **Ask the user first:** running the app (it moves real files), publishing the package, editing the `.bat` / `.vbs` launchers. Enforced by ask rules in `.claude/settings.json`. Also ask before changing the category rules in `DEFAULT_CATEGORIES` in `categorizer.py`; `tests/test_categories_pinned.py` fails until you update it, so the change can't slip through.
- **Always blocked** by `.claude/harness/hooks/guard.sh`: recursive deletes outside build and cache folders, force-push, `git reset --hard`, `git clean -f`, deleting branches. If one is truly needed, explain why and ask the user to run it.

## Known mistakes

<!-- One line per real mistake, phrased as what to do instead. Prefer turning a mistake into a check (run /retro). -->
- To test a check that looks at `file_index.json` or `file_indexer_config.ini`, use a scratch git repo with fake files, never the real ones. The deny rules only apply when the session starts in this repo; an agent once overwrote the real index this way.
- In a cloud session `gh pr view` fails (GitHub's GraphQL API is blocked). Use the REST API instead, for example `gh api repos/akholab/FileSorter/pulls/N`.
