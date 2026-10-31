import json
import sys
import types

import pytest

import safemove
from safemove import UndoLog, safe_move, trash_file, undo_move, unique_destination


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- unique_destination / safe_move ---------------------------------------

def test_free_name_is_unchanged(tmp_path):
    assert unique_destination(tmp_path / "a.pdf") == tmp_path / "a.pdf"


def test_taken_name_gets_a_number(tmp_path):
    write(tmp_path / "a.pdf")
    assert unique_destination(tmp_path / "a.pdf") == tmp_path / "a (2).pdf"


def test_numbers_keep_counting(tmp_path):
    write(tmp_path / "a.pdf")
    write(tmp_path / "a (2).pdf")
    assert unique_destination(tmp_path / "a.pdf") == tmp_path / "a (3).pdf"


def test_name_without_extension(tmp_path):
    write(tmp_path / "README")
    assert unique_destination(tmp_path / "README") == tmp_path / "README (2)"


def test_move_creates_missing_folders(tmp_path):
    src = write(tmp_path / "in" / "a.txt", "hello")
    final = safe_move(src, tmp_path / "out" / "deep" / "a.txt")
    assert final == tmp_path / "out" / "deep" / "a.txt"
    assert final.read_text() == "hello"
    assert not src.exists()


def test_move_never_overwrites(tmp_path):
    src = write(tmp_path / "in" / "a.txt", "new")
    existing = write(tmp_path / "out" / "a.txt", "old")
    final = safe_move(src, existing)
    assert final == tmp_path / "out" / "a (2).txt"
    assert existing.read_text() == "old"
    assert final.read_text() == "new"


def test_move_of_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        safe_move(tmp_path / "nope.txt", tmp_path / "out" / "nope.txt")
    assert not (tmp_path / "out").exists()


# --- UndoLog --------------------------------------------------------------

def test_log_survives_a_restart(tmp_path):
    path = tmp_path / "undo.json"
    log = UndoLog(path)
    log.record("moved", "/b/a.txt", {"original_path": "/a/a.txt"})
    log.record("kept", "/a/c.txt")
    reloaded = UndoLog(path)
    assert len(reloaded) == 2
    last = reloaded.pop_last()
    assert last["type"] == "kept" and last["file_path"] == "/a/c.txt"
    assert len(UndoLog(path)) == 1  # the pop was saved too


def test_log_keeps_only_the_newest_entries(tmp_path):
    log = UndoLog(tmp_path / "undo.json", max_entries=3)
    for i in range(5):
        log.record("kept", f"/f{i}")
    assert [e["file_path"] for e in UndoLog(tmp_path / "undo.json", max_entries=3).entries] == ["/f2", "/f3", "/f4"]


def test_default_limit_is_500(tmp_path):
    assert UndoLog(tmp_path / "undo.json").max_entries == 500


def test_empty_log_pops_none(tmp_path):
    assert UndoLog(tmp_path / "undo.json").pop_last() is None


@pytest.mark.parametrize("content", ["", "not json", "{}", "[1, 2]", '[{"type": "moved"}]'])
def test_bad_log_file_starts_empty(tmp_path, content):
    path = tmp_path / "undo.json"
    path.write_text(content)
    assert len(UndoLog(path)) == 0


def test_log_file_is_valid_json_and_leaves_no_temp_files(tmp_path):
    log = UndoLog(tmp_path / "undo.json")
    log.record("moved", "/b/ü.txt", {"original_path": "/a/ü.txt"})
    assert json.loads((tmp_path / "undo.json").read_text(encoding="utf-8"))[0]["file_path"] == "/b/ü.txt"
    assert [p.name for p in tmp_path.iterdir()] == ["undo.json"]


# --- undo_move ------------------------------------------------------------

def test_undo_puts_the_file_back(tmp_path):
    original = tmp_path / "in" / "a.txt"
    moved = write(tmp_path / "out" / "a.txt", "data")
    ok, msg, restored = undo_move({"file_path": str(moved), "details": {"original_path": str(original)}})
    assert ok and restored == original
    assert original.read_text() == "data" and not moved.exists()
    assert "moved back" in msg


def test_undo_does_not_overwrite_a_new_file_at_the_original_path(tmp_path):
    original = write(tmp_path / "in" / "a.txt", "newer")
    moved = write(tmp_path / "out" / "a.txt", "older")
    ok, msg, restored = undo_move({"file_path": str(moved), "details": {"original_path": str(original)}})
    assert ok and restored == tmp_path / "in" / "a (2).txt"
    assert original.read_text() == "newer"
    assert restored.read_text() == "older"
    assert "a (2).txt" in msg


def test_undo_reports_a_file_that_is_gone(tmp_path):
    ok, msg, restored = undo_move({"file_path": str(tmp_path / "gone.txt"),
                                   "details": {"original_path": str(tmp_path / "x.txt")}})
    assert not ok and restored is None and "not found" in msg.lower()


# --- trash_file -----------------------------------------------------------

def test_trash_hands_the_path_to_send2trash(tmp_path, monkeypatch):
    calls = []
    fake = types.ModuleType("send2trash")
    fake.send2trash = lambda p: calls.append(p)
    monkeypatch.setitem(sys.modules, "send2trash", fake)
    f = write(tmp_path / "a.txt")
    trash_file(f)
    assert calls == [str(f)]


def test_trash_without_the_library_refuses_instead_of_deleting(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "send2trash", None)  # makes the import fail
    f = write(tmp_path / "a.txt")
    with pytest.raises(RuntimeError, match="not deleted"):
        trash_file(f)
    assert f.exists()


def test_log_trims_in_memory_too(tmp_path):
    log = UndoLog(tmp_path / "undo.json", max_entries=3)
    for i in range(5):
        log.record("kept", f"/f{i}")
    assert len(log) == 3
    assert log.pop_last()["file_path"] == "/f4"


def test_moving_a_file_onto_itself_is_a_no_op(tmp_path):
    f = write(tmp_path / "a.txt", "data")
    assert safe_move(f, f) == f
    assert [p.name for p in tmp_path.iterdir()] == ["a.txt"]
    assert f.read_text() == "data"


def test_peek_does_not_remove(tmp_path):
    log = UndoLog(tmp_path / "undo.json")
    log.record("kept", "/f1")
    assert log.peek_last()["file_path"] == "/f1"
    assert len(log) == 1
    assert UndoLog(tmp_path / "empty.json").peek_last() is None


def test_undo_of_a_damaged_entry_reports_it_instead_of_crashing(tmp_path):
    moved = write(tmp_path / "out" / "a.txt")
    ok, msg, restored = undo_move({"file_path": str(moved), "details": {}})
    assert not ok and restored is None and "damaged" in msg
    assert moved.exists()
    ok, _, _ = undo_move({"file_path": str(moved)})
    assert not ok
