---
name: harness-update
description: Update this project's harness to the newest kit from MyClaudeSettings. Merges kit-owned files and keeps the project's edits, opens one pull request, and sends project edits back as one kit-feedback issue. Use only when the user types /harness-update.
disable-model-invocation: true
model: sonnet
effort: medium
---

The harness kit lives in the private repo `akholab/MyClaudeSettings` under `harness/kit/`. This skill brings a project up to its newest version the way Copier updates projects (https://copier.readthedocs.io/en/latest/updating/): a three-way merge of the old kit, the new kit and the project's copy, so the project's own edits stay and conflicts are left for review. `update.sh`, next to this file, does the merging.

Kit-owned: the hooks, `.claude/harness/README.md`, `.claude/agents/reviewer.md`, the kit's skills (this one too), the "Working on a task", "Writing code" and "Model and effort" sections of `AGENTS.md`, and the kit's hook entries in `.claude/settings.json`. Everything else belongs to the project: `check.sh`, `progress.md`, `research.md`, the rest of `AGENTS.md`, permission rules. Never edit those here.

## Steps

1. **Start.** The working tree must be clean; if not, ask the user to commit or stash, and wait. Create and switch to `harness-update` from the default branch (read its name from git). If that branch exists, ask before reusing it.

   Done when you're on `harness-update` with a clean tree.
2. **Find the kit.** Use the first that works:
   - A MyClaudeSettings checkout already on this machine: a sibling folder (`../MyClaudeSettings`, `../myclaudesettings`) or a repo attached to this cloud session. Fetch `main` with full history into `origin/main`: `git -C <dir> fetch --unshallow origin main:refs/remotes/origin/main` (drop `--unshallow` if `git -C <dir> rev-parse --is-shallow-repository` prints `false`). A plain `fetch origin main` doesn't create `origin/main` in a shallow clone.
   - Otherwise clone it to a temp folder with the user's GitHub login: `gh repo clone akholab/MyClaudeSettings <tmp>` or `git clone https://github.com/akholab/MyClaudeSettings.git <tmp>`.
   - If neither works, stop and tell the user how to give access: sign in with `gh auth login` on their computer, or attach MyClaudeSettings to the cloud session. Never ask for a token.

   NEW is `git -C <checkout> rev-parse origin/main` (for a fresh clone, `main`). Done when you have the checkout and NEW.
3. **Find the base.** Read `.claude/harness/kit-version`. If it's missing (projects installed before 2026-11), first make sure the project's own history is complete: if `git rev-parse --is-shallow-repository` prints `true`, run `git fetch --unshallow`, because a shallow clone makes every file look added in its oldest commit. Then take the date of the project's first commit that touched `.claude/harness/hooks/` (`git log --diff-filter=A --format=%cI -- .claude/harness/hooks | tail -1`) and use `git -C <checkout> rev-list -1 --before=<date> origin/main`. Remember that this base is a guess.

   If the base equals NEW, tell the user the harness is up to date and stop. Done when you have the base.
4. **Merge.** From the project root, run the new kit's script from the checkout, `<checkout>/harness/kit/.claude/skills/harness-update/update.sh <checkout> <base> <NEW> <report dir>` (never the project's own copy: the merge rewrites it while it runs), with a report dir outside the project (for example under the OS temp folder). Exit 3 means some files have conflicts; that's expected.
   - `HOOK-ADD` lines: add that hook's entry from the new kit's `harness/kit/.claude/harness/templates/settings.template.json` to `.claude/settings.json`, keeping every other key and rule. A hook entry the project removed on purpose isn't listed, so it stays removed.
   - `KEPT-DELETED` lines: the kit changed a file or section the project had removed. Leave it removed and list it in the pull request.
   - `CONFLICT` lines for a hook (`.sh`): the project's version stays in place and the merge with markers is in `<file>.merge`. Resolve it now, before step 5, and copy the result over the hook, then delete the `.merge` file; a hook with markers would block every command. If you can't resolve it, leave the hook as it is and list it.
   - Other `CONFLICT` lines: resolve only where one side clearly wins (the project's text is project-specific, or the kit's change is a plain improvement). Otherwise leave the markers for the user and list the file.
   - `EXISTS-DIFFERS` lines: the project already had its own file where the kit now adds one. It was left alone; its difference from the kit is in `feedback.diff`. List it in the pull request for the user to decide.
   - Make every `.sh` under `.claude/harness/hooks/` executable.
   - Write NEW to `.claude/harness/kit-version`.

   Done when every report line is handled or listed.
5. **Check.** Run `.claude/harness/check.sh`. If it fails because of the update, fix what the update broke by editing it back, never with `git checkout` or a reset. If it failed before the update too, say so in the pull request.
6. **Log it.** Add one line to the top of the session log in `progress.md`: the date, "harness-update", the base and NEW (short SHAs), and the number of files updated, added and left with conflicts.
7. **Send edits back.** Read `feedback.diff`. Keep the hunks that would help every project (a hook fix, a clearer rule, a reviewer improvement). Drop project-specific ones (the filled-in "Done means" line, project paths, project commands). If any are left, open **one** issue in `akholab/MyClaudeSettings` titled `kit-feedback: <project name> <date>`, labelled `kit-feedback` (skip the label if it can't be added), with each kept hunk, its file and one line on why it helps. Never edit MyClaudeSettings itself.

8. **Open the pull request** against the default branch, titled `Harness update <short NEW>`. In the description:
   - the report lines, grouped (updated, added, conflicts left, kept-deleted, removed upstream), and whether the base was a guess;
   - `check.diff` if it isn't empty, as suggested lines for `check.sh` that nobody has applied;
   - a link to the kit-feedback issue from step 7, if any.

   In a cloud session `gh pr create` can fail (GitHub's GraphQL API may be blocked); use the GitHub tools or `gh api repos/<owner>/<repo>/pulls -f title=... -f head=harness-update -f base=<default branch> -f body=...`. Never merge it.
Report to the user in a few lines: the pull request link, conflicts left, hooks added, suggested `check.sh` lines, and the issue link.
