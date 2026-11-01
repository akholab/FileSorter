"""Runs the real FileIndexer (not the GUI) with the Windows/GUI libraries
stubbed out, so the wiring of safemove, filewatch and learning is exercised.
Each test runs in its own temp folder, so no real data file is ever touched."""
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("watchdog")

for name in ("tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog",
             "psutil", "win32api", "win32gui"):
    sys.modules.setdefault(name, MagicMock())

import file_indexer  # noqa: E402


@pytest.fixture
def ix(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    indexer = file_indexer.FileIndexer()
    watched = tmp_path / "Downloads"
    watched.mkdir()
    indexer.file_monitor.monitored_paths.add(str(watched))
    indexer.watched = watched
    return indexer


def make(folder, name, text="x", age=60):
    f = folder / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    t = time.time() - age
    os.utime(f, (t, t))
    return f


def first_move(indexer, f):
    return next(s for s in indexer.suggest_organization(str(f)) if s["action"] == "move")


def move_to(indexer, f, folder):
    s = {"action": "move", "source": str(f), "destination": str(Path(folder) / f.name)}
    assert indexer.execute_suggestion(s, "move"), indexer.last_error
    return s


def test_move_renames_instead_of_overwriting(ix, tmp_path):
    docs = tmp_path / "Docs"
    make(docs, "a.pdf", "old")
    f = make(ix.watched, "a.pdf", "new")
    move_to(ix, f, docs)
    assert (docs / "a.pdf").read_text() == "old"
    assert (docs / "a (2).pdf").read_text() == "new"


def test_undo_survives_a_restart(ix, tmp_path):
    docs = tmp_path / "Docs"
    f = make(ix.watched, "a.pdf")
    move_to(ix, f, docs)
    restarted = file_indexer.FileIndexer()  # same folder, fresh process
    ok, msg = restarted.undo_last_action()
    assert ok, msg
    assert f.exists() and not (docs / "a.pdf").exists()


def test_a_file_still_being_written_is_not_moved(ix, tmp_path):
    f = make(ix.watched, "a.pdf", age=0)
    s = {"action": "move", "source": str(f), "destination": str(tmp_path / "Docs" / "a.pdf")}
    assert ix.execute_suggestion(s, "move") is False
    assert "still being written" in ix.last_error
    assert f.exists() and not (tmp_path / "Docs").exists()


def test_it_learns_after_two_moves(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    before = first_move(ix, make(ix.watched, "x.pdf"))
    assert "learned_count" not in before

    move_to(ix, make(ix.watched, "a.pdf"), taxes)
    assert "learned_count" not in first_move(ix, make(ix.watched, "b.pdf"))  # one vote is not enough

    move_to(ix, make(ix.watched, "b.pdf"), taxes)
    top = first_move(ix, make(ix.watched, "c.pdf"))
    assert Path(top["destination"]).parent == taxes
    assert top["learned_count"] == 2


def test_learning_is_per_extension_and_per_watched_folder(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    for n in "ab":
        move_to(ix, make(ix.watched, f"{n}.pdf"), taxes)
    assert "learned_count" not in first_move(ix, make(ix.watched, "c.jpg"))
    other = tmp_path / "Desktop"
    ix.file_monitor.monitored_paths.add(str(other))
    assert "learned_count" not in first_move(ix, make(other, "c.pdf"))


def test_undo_takes_back_what_the_move_taught(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    move_to(ix, make(ix.watched, "a.pdf"), taxes)
    move_to(ix, make(ix.watched, "b.pdf"), taxes)
    ok, _ = ix.undo_last_action()
    assert ok
    assert "learned_count" not in first_move(ix, make(ix.watched, "c.pdf"))


def test_keep_counts_as_a_vote_and_skip_does_not(ix):
    for n in "ab":
        f = make(ix.watched, f"{n}.zip")
        assert ix.execute_suggestion({"action": "keep", "source": str(f)}, "keep")
    suggestions = ix.suggest_organization(str(make(ix.watched, "c.zip")))
    assert suggestions[0]["action"] == "keep" and suggestions[0]["learned_count"] == 2
    # nothing in the code path for "skip" calls the learner, so it never votes
    assert sum(e["count"] for d in ix.learner.votes.values() for e in d.values()) == 2


def test_a_bulk_move_counts_once_per_kind_of_file(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    seen = set()
    for n in "abc":
        f = make(ix.watched, f"{n}.pdf")
        ix.learn_from_move(f, taxes / f.name, seen)
    assert sum(e["count"] for d in ix.learner.votes.values() for e in d.values()) == 1


def test_learned_choices_survive_a_restart(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    for n in "ab":
        move_to(ix, make(ix.watched, f"{n}.pdf"), taxes)
    restarted = file_indexer.FileIndexer()
    restarted.file_monitor.monitored_paths.add(str(ix.watched))
    top = first_move(restarted, make(ix.watched, "c.pdf"))
    assert Path(top["destination"]).parent == taxes


def test_initial_scan_skips_partial_downloads(ix):
    assert not ix.should_process_file(str(ix.watched / "movie.mp4.crdownload"))
    assert ix.should_process_file(str(ix.watched / "movie.mp4"))


def test_a_learning_failure_never_makes_a_finished_move_look_failed(ix, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("learner broke")
    monkeypatch.setattr(ix.learner, "vote", boom)
    f = make(ix.watched, "a.pdf")
    s = {"action": "move", "source": str(f), "destination": str(tmp_path / "Docs" / "a.pdf")}
    assert ix.execute_suggestion(s, "move") is True
    assert (tmp_path / "Docs" / "a.pdf").exists()
    ok, _ = ix.undo_last_action()  # the move still has an undo entry
    assert ok and f.exists()


def test_moving_a_file_onto_itself_teaches_nothing(ix):
    f = make(ix.watched, "a.pdf")
    s = {"action": "move", "source": str(f), "destination": str(f)}
    assert ix.execute_suggestion(s, "move")
    assert ix.learner.votes == {}


def test_a_bulk_keep_counts_once_per_kind_of_file(ix):
    seen = set()
    for n in "abc":
        ix.learn_from_move(make(ix.watched, f"{n}.zip"), None, seen)
    assert sum(e["count"] for d in ix.learner.votes.values() for e in d.values()) == 1


def test_indexer_writes_and_uses_rules_toml(ix):
    assert Path("rules.toml").exists()  # created in the temp work folder
    assert ix.rules_error is None


def test_indexer_uses_edited_rules(tmp_path, monkeypatch):
    work = tmp_path / "w2"
    work.mkdir()
    monkeypatch.chdir(work)
    (work / "rules.toml").write_text('[categories.taxes]\nextensions = [".pdf"]\nfolders = ["Taxes"]\n', encoding="utf-8")
    indexer = file_indexer.FileIndexer()
    assert indexer.rules_error is None
    assert indexer.categorize_file(str(tmp_path / "a.pdf")) == "taxes"


def test_indexer_falls_back_on_broken_rules(tmp_path, monkeypatch):
    work = tmp_path / "w3"
    work.mkdir()
    monkeypatch.chdir(work)
    (work / "rules.toml").write_text("[categories.taxes\n", encoding="utf-8")
    indexer = file_indexer.FileIndexer()
    assert "line" in indexer.rules_error
    assert indexer.categorize_file(str(tmp_path / "a.pdf")) == "documents"


def test_preview_lists_files_and_moves_nothing(ix):
    pdf = make(ix.watched, "a.pdf")
    odd = make(ix.watched, "notes.xyz")
    make(ix.watched, "big.crdownload")  # unfinished downloads are left out
    before = sorted(p.name for p in ix.watched.rglob("*"))
    rows = {Path(f).name: (folder, reason) for f, folder, reason in ix.preview_folder(str(ix.watched))}
    assert set(rows) == {"a.pdf", "notes.xyz"}
    assert Path(rows["a.pdf"][0]) == ix.watched / "Documents"
    assert rows["a.pdf"][1] == "category: documents"
    assert rows["notes.xyz"] == (None, "no category matched")
    assert sorted(p.name for p in ix.watched.rglob("*")) == before
    assert pdf.exists() and odd.exists()
    assert ix.suggestions_queue == []  # preview doesn't queue anything


def test_preview_shows_learned_choice(ix, tmp_path):
    taxes = tmp_path / "Taxes"
    taxes.mkdir()
    for name in ("1.pdf", "2.pdf"):
        move_to(ix, make(ix.watched, name), taxes)
    make(ix.watched, "3.pdf")
    [(_, folder, reason)] = ix.preview_folder(str(ix.watched))
    assert (Path(folder), reason) == (taxes, "your usual")


def test_preview_leaves_out_files_already_sorted(ix):
    f = make(ix.watched, "a.pdf")
    move_to(ix, f, ix.watched / "Documents")  # now indexed, inside the watched folder
    make(ix.watched, "b.pdf")
    names = [Path(p).name for p, _, _ in ix.preview_folder(str(ix.watched))]
    assert names == ["b.pdf"]


def test_rules_warning_reads_as_a_sentence(tmp_path, monkeypatch):
    work = tmp_path / "w4"
    work.mkdir()
    monkeypatch.chdir(work)
    (work / "rules.toml").write_text("[categories.taxes\n", encoding="utf-8")
    msg = file_indexer.FileIndexer().rules_warning()
    assert msg.startswith("Rules not loaded, so the built-in categories are used.")
    assert "rules.toml" in msg


def test_domain_rule_wins_over_learned_and_category(tmp_path, monkeypatch):
    work = tmp_path / "w5"
    work.mkdir()
    monkeypatch.chdir(work)
    bank = tmp_path / "Bank"
    (work / "rules.toml").write_text(
        '[categories.docs]\nextensions = [".pdf"]\nfolders = ["Docs"]\n'
        f'[[domain_rules]]\ndomain = "mybank.com"\nfolder = "{bank.as_posix()}"\n',
        encoding="utf-8")
    indexer = file_indexer.FileIndexer()
    assert indexer.rules_error is None
    watched = tmp_path / "Downloads"
    watched.mkdir()
    indexer.file_monitor.monitored_paths.add(str(watched))
    taxes = tmp_path / "Taxes"
    taxes.mkdir()
    for name in ("1.pdf", "2.pdf"):
        move_to(indexer, make(watched, name), taxes)  # learned: pdfs go to Taxes
    make(watched, "statement.pdf")
    make(watched, "other.pdf")
    hosts = {"statement.pdf": ["files.mybank.com", "www.mybank.com"]}
    monkeypatch.setattr(file_indexer.download_source, "read_hosts", lambda p: hosts.get(Path(p).name, []))
    rows = {Path(f).name: (Path(folder), reason) for f, folder, reason in indexer.preview_folder(str(watched))}
    assert rows["statement.pdf"] == (bank, "your rule: mybank.com")
    assert rows["other.pdf"] == (taxes, "your usual")


def test_moves_of_downloads_are_learned_per_website(ix, tmp_path, monkeypatch):
    bank = tmp_path / "Bank"
    bank.mkdir()
    monkeypatch.setattr(file_indexer.download_source, "read_hosts", lambda p: ["www.mybank.com"])
    for name in ("1.pdf", "2.pdf"):
        move_to(ix, make(ix.watched, name), bank)
    assert all(k.endswith("|mybank.com") for k in ix.learner.votes)
    assert Path(first_move(ix, make(ix.watched, "3.pdf"))["destination"]).parent == bank
    monkeypatch.setattr(file_indexer.download_source, "read_hosts", lambda p: [])
    assert Path(first_move(ix, ix.watched / "3.pdf")["destination"]).parent != bank
    ok, _ = ix.undo_last_action()  # undo takes the website vote back
    assert ok and sum(e["count"] for d in ix.learner.votes.values() for e in d.values()) == 1
