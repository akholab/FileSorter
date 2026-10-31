# Agent harness

This folder keeps coding agents honest in this project. It came from [MyClaudeSettings](https://github.com/akholab/MyClaudeSettings) (see `harness/` there).

| File | What it does |
|---|---|
| `check.sh` | One command that says whether the project is healthy. Exit 0 means pass. |
| `progress.md` | Goal, open tasks, and a session log, so each new session picks up where the last one stopped. |
| `hooks/guard.sh` | Runs before every shell command: blocks recursive deletes (except build and cache folders), force-push, `git reset --hard`, `git clean -f` and branch deletes, even when wrapped in `sudo`, `bash -c` or `git -C`. |
| `hooks/session-start.sh` | Runs when a Claude Code session starts: shows Claude the progress file. |
| `hooks/stop-check.sh` | Runs when Claude tries to finish: runs `check.sh` and sends Claude back if it fails, up to 3 times per session. Skips when nothing changed. |
| `.state/` | Scratch files for the hooks. Git-ignored. |

The hooks and the ask/deny permission rules are in `.claude/settings.json`. The map for agents is `AGENTS.md` at the project root. `/retro` (in `.claude/skills/retro/`) reviews a session and proposes harness fixes. The `reviewer` subagent (`.claude/agents/reviewer.md`) reviews each change before Claude says it's done; it reads but never edits.

**Turn the gate off for a while:** remove the `Stop` entry from `.claude/settings.json`.
**Run a blocked command anyway:** run it yourself in your own terminal.
**Run setup again:** copy the kit in again.

**Windows:** the hooks are bash scripts. Claude Code runs them through Git Bash; without Git Bash installed they fail with a non-blocking error, and the gate and guard are off.
