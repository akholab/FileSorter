# FileSorter: making it smarter

Research notes, 31 Oct 2026

## Summary

Today FileSorter picks a category from the file extension, falls back to filename keywords, and suggests moving the file into a subfolder next to where it already is (for example `Downloads/Documents`). The intelligent organizers on the market add four things on top of that:

- They look at what the file actually is and where it came from.
- They let you preview and undo safely.
- They learn from your choices.
- Some ask a local AI model when the rules can't decide.

My recommendation is to build in that order. The safety and signal work is cheap, adds no new privacy risk, and makes a later AI step much more useful.

## What FileSorter does today

- **Category:** a hardcoded table in `FileIndexer.categories` with 6 categories. The extension is checked first, then keywords in the filename, otherwise the file is `misc`.
- **Destination:** always `file.parent / <category folder>`. It never suggests an existing folder somewhere else on the disk.
- **Trigger:** watchdog's `on_created` and `on_moved`. A file is queued the moment it appears, with only a 1 KB size check. Nothing waits for a download or copy to finish.
- **Safety:** moves use `shutil.move` with no check for a file of the same name at the destination. The undo history is a list in memory, so it is lost when the app restarts. Delete is permanent.
- **Learning:** none. What you accept or skip is never used again.

## What the best tools do

| Tool | What stands out |
|---|---|
| [Hazel](https://noodlesoft.com) (Mac, rules) | Rules match on name, date, type and the **site a file came from**. It renames files from patterns, sorts them into subfolders and cleans up the Trash. |
| [organize](https://organize.readthedocs.io/) (Python, cross-platform, YAML rules) | Filters on extension, name, **text extracted from PDF and DOCX**, **EXIF** and **duplicates**. `organize sim` shows every change before anything is touched. Moves have conflict-resolution options. |
| [File Juggler](https://www.softpedia.com/get/System/File-Management/FileJuggler.shtml) and [DropIt](https://sourceforge.net/projects/dropit/) (Windows, rules) | Rule-based sorting, including on text contents, with a log. |
| [Sparkle](https://www.igeeksblog.com/organize-mac-with-sparkle-ai/) (Mac, AI) | Keeps files from the last 3 days in **Recents** and only sorts older files into an AI Library. Files in its Manual Library are never re-sorted. It reads only file names, so vaguely named files get misplaced, and you can't define your own categories. |
| [AI File Sorter](https://gittrend.io/repo/hyperfield/ai-file-sorter) (cross-platform, open source) | A local text or vision LLM suggests categories and names in a **review table** that you edit before anything moves. It can **undo the last run**. |
| [Local File Organizer](https://pypi.org/project/local-file-organizer/) (Python, open source) | Uses Ollama by default (Qwen 2.5 3B for text, Qwen 2.5-VL 7B for images) and handles 80+ formats. It has a `preview` command, undo and redo history, hash and semantic dedup, and PARA and Johnny Decimal layouts. It **learns from your preferences**. |

**Patterns they share:**

- Look at content and metadata, not just the extension.
- Preview before acting.
- Keep undo working across runs.
- Run the AI locally by default and make cloud models opt-in.
- Let the user override a suggestion, and remember the override.

## Suggested improvements, in priority order

### Tier 1: safe and solid (no AI)

1. **Wait until a file is finished.** Skip partial-download names such as `.crdownload`, `.part`, `.download` and `.tmp`. Queue a file only after its size and modified time have stayed the same for a few seconds, or once no process holds it open (psutil is already a dependency). Without this, the app suggests moving files that are still downloading ([discussion](https://backiee.wasmer.app/https_programmers_stackexchange_com/questions/200803/watching-file-changes-additions-removal-but-with-an-eye-on-partial-transfer)).
2. **Make moves safe.** When a file with the same name is already at the destination, rename the new one (`name (2).pdf`) or skip it. Never overwrite. Keep the undo log on disk as a JSON Lines file so undo still works after a restart. Send deleted files to the system Trash instead of deleting them permanently.
3. **Keep rules in a file the user can edit**, in TOML or YAML, instead of the hardcoded table. Add a **preview mode** that lists every planned move before any happen, like `organize sim`.
4. **Split the categorizer from the GUI and add pytest tests.** This is already on the progress list, and every later item depends on it.

### Tier 2: smarter signals (still no AI)

5. **Detect the real file type from its content.** Google's [Magika](https://securityresearch.google/magika/) model is a few MB, takes about 5 ms per file on a CPU, covers more than 200 types and reaches about 99% precision. It catches files whose extension is wrong or missing.
6. **Use where the file came from.** Read the download URL from `Zone.Identifier` (`HostUrl`) on Windows, `kMDItemWhereFroms` on macOS and `user.xdg.origin.url` on Linux. The [whence](https://github.com/mignon-p/whence) tool documents all three. That makes a rule like "anything from my bank's website goes to Finance" possible, which is Hazel's best-known trick.
7. **Use metadata and content.** Use the EXIF date and camera to tell photos from screenshots. Use keywords in a PDF's text (invoice, receipt, contract) to sort documents.
8. **Learn from your choices.** Record each accept, skip and manual move along with the file's features (type, source domain, keywords). Next time, rank destinations by what you did before. This runs locally, costs little, and is the change most likely to make the app feel smart.
9. **Suggest folders you already use**, such as `~/Documents/Finance/2026`, not just a new subfolder beside the file.
10. **Detect duplicates** by comparing size first and then a hash, and offer to keep one copy.
11. **Add a grace period, as Sparkle does.** Leave new files alone for a set number of days, so Downloads is tidied only once files have gone cold.

### Tier 3: optional AI

12. **Fall back to a local LLM.** When the rules and your history can't decide (low confidence), send the file name, a text snippet or a thumbnail to a local model through Ollama. Ask for the answer as JSON with a fixed schema (category, folder, new name, confidence) at temperature 0 ([Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)). Show the result in the review table. At first, never move a file on the AI's answer alone. Cloud models stay opt-in.
13. **Suggest better names**, such as `2026-10-31 Invoice ACME.pdf`, using the date and content extracted from the file.
14. **Offer optional layout templates** such as [Johnny Decimal](https://johnnydecimal.com/documentation/areas-and-categories.md) (areas, categories and IDs, three levels deep) or PARA, for users who want a complete system rather than folders by file type.

## Design questions to settle before building

- Should the app ever move files on its own, or always ask? It has an `auto_sort` setting today.
- Is a local AI model acceptable on every device, given the disk space and RAM Ollama needs? Is a cloud model ever acceptable?
- Where should the rules, the undo log and the learned history live, so they sync across your devices?
- Should folders be organized by file type (Images, Documents) or by topic (Finance, Work, Travel)?

## Sources

- Hazel: https://noodlesoft.com
- organize docs: https://organize.readthedocs.io/
- AI File Sorter: https://gittrend.io/repo/hyperfield/ai-file-sorter
- Local File Organizer: https://pypi.org/project/local-file-organizer/
- Sparkle review: https://www.igeeksblog.com/organize-mac-with-sparkle-ai/
- File Juggler: https://www.softpedia.com/get/System/File-Management/FileJuggler.shtml
- DropIt: https://sourceforge.net/projects/dropit/
- Magika: https://securityresearch.google/magika/
- whence (download-source metadata): https://github.com/mignon-p/whence
- Discussion on detecting partially written files: https://backiee.wasmer.app/https_programmers_stackexchange_com/questions/200803/watching-file-changes-additions-removal-but-with-an-eye-on-partial-transfer
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Johnny Decimal: https://johnnydecimal.com/documentation/areas-and-categories.md
