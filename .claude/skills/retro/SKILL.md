---
name: retro
description: Review a past coding session and propose harness fixes (AGENTS.md, check.sh, guard rules, hooks) so the same mistakes can't recur. Use only when the user types /retro.
disable-model-invocation: true
---

Adapted from mattpocock/skills `retro` and `writing-for-agents` (MIT, © 2026 Matt Pocock) for the agent harness kit.

A retro improves the **harness** (the files that steer and check agents), using the session and the code as evidence. It never edits application code.

## Steps

1. **Pick the session.** Use the one the user names; otherwise the current one. Read its evidence: the conversation, `git log` and diffs since the session began, `check` output, and Stop-hook or guard blocks. Done when you can list what the agent got wrong or struggled with.
2. **Find candidates.** For each problem, ask "what harness change would have prevented this?" Look in these areas:
   - **Checks:** could a lint rule, type check, test or file-layout check in `.claude/harness/check.sh` have caught it? A mechanical rule always beats a written one.
   - **Guard and permissions:** did the agent try something risky that `.claude/harness/hooks/guard.sh` or the `permissions` in `.claude/settings.json` should stop or ask about?
   - **Navigation:** did it struggle to find a file, command or doc? A one-line pointer in `AGENTS.md` may fix it.
   - **Known mistakes:** a judgement call no check can make goes in `AGENTS.md` under "Known mistakes", one line, phrased as what to do.
   - **No-ops and bloat:** lines in `AGENTS.md` that didn't change what the agent did, repeat what the code or config already shows, or tell the model something it does by default. Propose deleting them.
   - **Missing information:** logs, commands or access the agent needed but didn't have.
   - **Progress handoff:** did the session start without knowing what the last one did? Fix `.claude/harness/progress.md`.

   Done when every problem from step 1 has a candidate, or a note that no harness change would help.
3. **Present a numbered list, most severe first.** One line each: the problem, the fix, and the file it changes. Then ask the user which numbers to apply. Wait for the answer.
4. **Apply only the chosen numbers.** Keep `AGENTS.md` near 100 lines: a map with pointers, not a manual. When a check or guard rule replaces a written rule, delete the written one.
5. **Verify.** Run `.claude/harness/check.sh`. For a new check, show that it fails on the original mistake and passes now. For a guard change, run the guard with a sample command and show the block. Done when `check` passes.
6. **Log it.** Add one line to the session log in `.claude/harness/progress.md`: the date, "retro", and the fixes applied. If a progress task says to run `/retro`, tick it.

## Writing rules for harness files

- Steps first, each ending in a checkable "done when".
- State the behaviour you want; use "never" only for hard guardrails.
- Each fact lives in one place. Point to it rather than copying it.
- Don't restate what `package.json`, config files or the folder layout already show.
- Delete a line if removing it wouldn't change what the agent does.
