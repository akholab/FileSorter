# Agent harness

This folder keeps coding agents honest in this project. It came from [MyClaudeSettings](https://github.com/akholab/MyClaudeSettings) (see `harness/` there).

| File | What it does |
|---|---|
| `check.sh` | One command that says whether the project is healthy. Exit 0 means pass. |
| `progress.md` | Goal, open tasks, and a session log, so each new session picks up where the last one stopped. |
| `hooks/guard.sh` | Runs before every shell command: blocks recursive deletes (except build and cache folders), force-push, `git reset --hard`, `git clean -f` and branch deletes, even when wrapped in `sudo`, `bash -c` or `git -C`. |
| `hooks/reviewer-bash.sh` | Runs only inside the `reviewer` subagent (from its frontmatter, and from `guard.sh`): allows read-only git commands and blocks everything else, so the reviewer can't change files. |
| `hooks/session-start.sh` | Runs when a Claude Code session starts: shows Claude the progress file, and asks you to trust the folder if Claude Code hasn't yet (it skips agent hooks until you do). |
| `hooks/stop-check.sh` | Runs when Claude tries to finish: runs `check.sh` and sends Claude back if it fails, up to 3 times per session. Skips when nothing changed. |
| `kit-version` | The MyClaudeSettings commit this harness was installed or last updated from. |
| `.state/` | Scratch files for the hooks. Git-ignored. |

The hooks and the ask/deny permission rules are in `.claude/settings.json`. The map for agents is `AGENTS.md` at the project root. `/retro` (in `.claude/skills/retro/`) reviews a session and proposes harness fixes. `/cleanup` (in `.claude/skills/cleanup/`) fixes drift in harness and doc files and opens one pull request; schedule it weekly with `/schedule` from Claude Code on your computer, or at claude.ai/code/routines. `research.md` at the project root keeps outside facts with sources and dates. The `reviewer` subagent (`.claude/agents/reviewer.md`) reviews each change before Claude says it's done; it reads but never edits.

**Turn the gate off for a while:** remove the `Stop` entry from `.claude/settings.json`.
**Run a blocked command anyway:** run it yourself in your own terminal.
**Update to the newest kit:** type `/harness-update`. It merges the new kit into the hooks, skills, reviewer and the harness sections of `AGENTS.md`, keeps your edits, and opens a pull request; `check.sh`, `progress.md` and permission rules are never touched. Edits worth sharing go back to MyClaudeSettings as one `kit-feedback` issue.
**Run setup again:** copy the kit in again.

**Windows:** the hooks are bash scripts. Claude Code runs them through Git Bash; without Git Bash installed they fail with a non-blocking error, and the gate and guard are off.
