# Agent harness

This folder keeps coding agents honest in this project. It came from [MyClaudeSettings/harness](https://github.com/akholab/MyClaudeSettings/tree/main/harness).

| File | What it does |
|---|---|
| `check.sh` | One command that says whether the project is healthy. Exit 0 means pass. |
| `progress.md` | Goal, open tasks, and a session log, so each new session picks up where the last one stopped. |
| `hooks/session-start.sh` | Runs when a Claude Code session starts: shows Claude the progress file. |
| `hooks/stop-check.sh` | Runs when Claude tries to finish: runs `check.sh` and sends Claude back if it fails, up to 3 times per session. Skips when nothing changed. |
| `.state/` | Scratch files for the hooks. Git-ignored. |

The hooks are registered in `.claude/settings.json`. The map for agents is `AGENTS.md` at the project root.

**Turn the gate off for a while:** remove the `Stop` entry from `.claude/settings.json`.
**Run setup again:** copy the kit in again.
