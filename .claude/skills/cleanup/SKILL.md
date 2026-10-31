---
name: cleanup
description: Scheduled clean-up of harness drift. Fixes broken pointers, stale tasks and an overlong log in the harness and doc files, lists code and research problems, and opens one pull request. Use only when the user or a scheduled task types /cleanup.
disable-model-invocation: true
model: sonnet
effort: medium
---

Idea from OpenAI's "garbage collection" and "doc-gardening" agents (https://openai.com/index/harness-engineering/): pay down drift in small, regular pull requests. Meant to run weekly as a Claude Code scheduled task, but works the same when typed by hand.

You may run with nobody watching, so you can't ask anyone. Change only what "Fix" allows, never merge, and when in doubt list instead of fixing.

## Steps

1. **Start.** Read `AGENTS.md` (boundaries, never-edit paths) and `.claude/harness/progress.md`.
   - If a cleanup pull request (branch `claude/cleanup-*`) is still open, work on that branch and update that pull request instead of opening another. Merge the default branch into it first if it's behind (never rebase or force-push).
   - Otherwise start a new branch `claude/cleanup-<YYYY-MM-DD>` from the latest default branch.
   - Cloud clones are shallow. Fetch more history (`git fetch --depth=500 origin <default branch>`); if that fails, treat every "is it merged" or "was it renamed" question as unsure.
   - Run `.claude/harness/check.sh` once and note whether it passes before you change anything.

   Done when you're on the branch and know the baseline `check` result.
2. **Fix** only these:
   - In `AGENTS.md`, `CLAUDE.md`, the project's top-level `README*` and `docs/`: a path, command or file pointed to that no longer exists. Fix the pointer when `git log --follow` shows where it moved; otherwise remove the line and list it.
   - Broken relative links in markdown files. In `research.md` and in decision logs (tables or files of past decisions), only repoint a link whose new location is certain; never delete lines there, list them instead.
   - Tasks in `progress.md` that are done (merged, or the session log says so) but still unticked: tick them.

   Never touch application code, never-edit paths from `AGENTS.md`, `.claude/settings.json`, `.claude/harness/hooks/`, `.claude/harness/check.sh` or `.claude/agents/`. Done when each fix is made or moved to the list.
3. **List** (don't fix) for the pull request description:
   - **Dead code:** functions, files or settings with no users. Grep the whole tree (tests, config, string references) before listing; say what you checked.
   - **Shortcuts:** `git grep -nE '(#|//|/[*]|<!--|--|^[[:space:]]*[*]) ?shortcut:'`. List any that names no upgrade trigger or whose limit the project has passed.
   - **Stale research:** dated headings in `research.md`: `grep -nE '^#{2,3} .*\((checked|researched) [0-9]{4}-[0-9]{2}-[0-9]{2}\)' research.md`. List each topic whose date is more than 6 months old. A `##` topic whose `###` subtopics carry their own dates is judged by the subtopics.
   - Anything from step 2 you weren't sure enough to fix.

   Every item names a file and line and says why. Done when the list is written.
4. **Stop if there's nothing.** No fixes and an empty list, or the same list as the open cleanup pull request with no new fixes: don't commit or push; reply "Nothing new to clean up" and stop.
5. **Log it.** Add one line to the top of the session log in `progress.md`: the date, "cleanup", and the number of fixes and listed items. Then, if the log is longer than 20 lines, keep the newest 20.
6. **Check.** Run `check` again. If it fails and it passed in step 1, fix or revert your own edits by editing them back. If it already failed in step 1, say so at the top of the pull request description.
7. **Open or update the pull request** against the default branch, titled `Cleanup <YYYY-MM-DD>`, with the fixes made and the list from step 3. In a cloud session `gh pr create` can fail (GitHub's GraphQL API may be blocked): use the GitHub tools if you have them, or the REST API, `gh api repos/<owner>/<repo>/pulls -f title=... -f head=<branch> -f base=<default branch> -f body=...`. Never merge it. Done when the pull request is open or updated; if you can't open it, say so plainly with the branch name.
