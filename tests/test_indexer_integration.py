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
