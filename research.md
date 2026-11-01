# Research notes

Outside facts worth keeping for this project: how a library or API behaves, prices and limits, what other projects do. Agents add to it whenever a task depends on such a fact.

Rules:

- Newest topic first. Each topic starts with `## <topic> (checked YYYY-MM-DD)`. Update the date when you re-check it.
- Every claim links to its source. Prefer official docs and primary sources.
- Only what's worth keeping. Notes for a single task stay in the task.
- `/cleanup` lists topics whose date is more than 6 months old, so they get re-checked.

---

## Test tools: coverage and mutmut (checked 2026-11-01)

- coverage 7.17.0 (22 Oct 2026) needs Python 3.11 or later. [pypi.org/project/coverage](https://pypi.org/project/coverage/)
- mutmut 3.8.1 (28 Oct 2026) needs `fork`, so on Windows it only runs inside WSL. Use `only_mutate` in `setup.cfg`, or `mutmut run "module*"`, to limit a run to the changed files. [pypi.org/project/mutmut](https://pypi.org/project/mutmut/)

## Windows download mark and file moves (checked 2026-11-01)

- Browsers save the download source in a `Zone.Identifier` NTFS stream (`[ZoneTransfer]`, `ZoneId`, `HostUrl`, `ReferrerUrl`). Explorer sets `ReferrerUrl` to the archive's path for files extracted from a zip. [digital-detective.net](https://www.digital-detective.net/forensic-analysis-of-zone-identifier-stream/), [Wikipedia: Mark of the Web](https://en.wikipedia.org/wiki/Mark_of_the_Web)
- `shutil.move` renames when it can, which keeps the stream. Across drives it copies, and on Windows copying does not keep alternate data streams. FAT32 and exFAT can't hold streams at all. So read the mark before moving. [docs.python.org: shutil](https://docs.python.org/3/library/shutil.html)

## Making FileSorter smarter (checked 2026-10-31)

See [docs/research/smarter-filesorter.md](docs/research/smarter-filesorter.md): best practices and other intelligent file managers, with sources.
