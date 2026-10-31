import configparser
import json
import os
from pathlib import Path

import pytest

from learning import KEEP, Learner, get_threshold


@pytest.fixture
def root(tmp_path):
    d = tmp_path / "Downloads"
    d.mkdir()
    return d


def make_learner(tmp_path, threshold=2):
    return Learner(tmp_path / "learned.json", threshold)


# --- grouping ---------------------------------------------------------------

def test_group_is_extension_plus_watched_folder(root):
    a = Learner.key_for(root / "a.PDF", [root])
    assert a == Learner.key_for(root / "b.pdf", [root])
    assert a != Learner.key_for(root / "b.docx", [root])
    assert a != Learner.key_for(root.parent / "Desktop" / "a.pdf", [root.parent / "Desktop"])


def test_files_in_subfolders_belong_to_the_watched_folder(root):
    assert Learner.key_for(root / "sub" / "deep" / "a.pdf", [root]) == Learner.key_for(root / "a.pdf", [root])


def test_nested_watched_folders_use_the_closest_one(root):
    inner = root / "Work"
    assert Learner.key_for(inner / "a.pdf", [root, inner]) == Learner.key_for(inner / "b.pdf", [inner])
    assert Learner.key_for(inner / "a.pdf", [root, inner]) != Learner.key_for(root / "a.pdf", [root, inner])


def test_similarly_named_folder_is_not_inside_the_watched_one(root):
    other = root.parent / "Downloads-old"
    assert Learner.key_for(other / "a.pdf", [root]) != Learner.key_for(root / "a.pdf", [root])


def test_without_a_watched_folder_the_files_own_folder_is_used(root):
    assert Learner.key_for(root / "a.pdf", []) == Learner.key_for(root / "b.pdf", [])
    assert Learner.key_for(root / "a.pdf", []) != Learner.key_for(root / "sub" / "b.pdf", [])


def test_files_without_an_extension_are_grouped_too(root):
    assert Learner.key_for(root / "README", [root]) == Learner.key_for(root / "LICENSE", [root])


# --- threshold and majority ---------------------------------------------------

def test_one_vote_is_not_enough(tmp_path, root):
    L = make_learner(tmp_path)
    L.vote(root / "a.pdf", tmp_path / "Docs", [root])
    assert L.usual(root / "b.pdf", [root]) is None


def test_two_votes_earn_the_top_spot(tmp_path, root):
    L = make_learner(tmp_path)
    docs = tmp_path / "Docs"
    L.vote(root / "a.pdf", docs, [root])
    L.vote(root / "b.pdf", docs, [root])
    assert L.usual(root / "c.pdf", [root]) == (str(docs), 2)


def test_threshold_is_configurable(tmp_path, root):
    L = make_learner(tmp_path, threshold=3)
    for n in "abc":
        assert L.usual(root / "x.pdf", [root]) is None
        L.vote(root / f"{n}.pdf", tmp_path / "Docs", [root])
    assert L.usual(root / "x.pdf", [root]) == (str(tmp_path / "Docs"), 3)


def test_only_the_most_voted_folder_wins(tmp_path, root):
    L = make_learner(tmp_path)
    docs, taxes = tmp_path / "Docs", tmp_path / "Taxes"
    for _ in range(2):
        L.vote(root / "a.pdf", docs, [root])
    for _ in range(3):
        L.vote(root / "a.pdf", taxes, [root])
    assert L.usual(root / "z.pdf", [root]) == (str(taxes), 3)


def test_a_tie_goes_to_the_most_recent_choice(tmp_path, root):
    L = make_learner(tmp_path)
    docs, taxes = tmp_path / "Docs", tmp_path / "Taxes"
    for _ in range(2):
        L.vote(root / "a.pdf", docs, [root])
    for _ in range(2):
        L.vote(root / "a.pdf", taxes, [root])
    assert L.usual(root / "z.pdf", [root])[0] == str(taxes)


def test_other_groups_are_not_affected(tmp_path, root):
    L = make_learner(tmp_path)
    for _ in range(2):
        L.vote(root / "a.pdf", tmp_path / "Docs", [root])
    assert L.usual(root / "a.jpg", [root]) is None


def test_keep_can_be_the_usual_choice(tmp_path, root):
    L = make_learner(tmp_path)
    for _ in range(2):
        L.vote(root / "a.zip", KEEP, [root])
    assert L.usual(root / "b.zip", [root]) == (KEEP, 2)


# --- undo ---------------------------------------------------------------------

def test_retract_takes_a_vote_back(tmp_path, root):
    L = make_learner(tmp_path)
    key, dest = L.vote(root / "a.pdf", tmp_path / "Docs", [root])
    L.vote(root / "b.pdf", tmp_path / "Docs", [root])
    L.retract(key, dest)
    assert L.usual(root / "c.pdf", [root]) is None
    L.retract(key, dest)
    assert L.votes == {}
    L.retract(key, dest)  # retracting from nothing is harmless
    assert L.votes == {}


# --- saving ---------------------------------------------------------------------

def test_votes_survive_a_restart(tmp_path, root):
    L = make_learner(tmp_path)
    for _ in range(2):
        L.vote(root / "a.pdf", tmp_path / "Dökuments", [root])
    again = make_learner(tmp_path)
    assert again.usual(root / "z.pdf", [root]) == (str(tmp_path / "Dökuments"), 2)
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == ["learned.json"]


@pytest.mark.parametrize("content", ["", "nope", "[]", '{"votes": []}', '{"votes": {"k": 5}}',
                                     '{"votes": {"k": {"d": {"count": "x"}}}}',
                                     '{"votes": {"k": {"d": {"count": 0}}}}'])
def test_bad_file_starts_empty(tmp_path, content):
    (tmp_path / "learned.json").write_text(content)
    assert make_learner(tmp_path).votes == {}


def test_file_format(tmp_path, root):
    L = make_learner(tmp_path)
    key, dest = L.vote(root / "a.pdf", tmp_path / "Docs", [root])
    data = json.loads((tmp_path / "learned.json").read_text(encoding="utf-8"))
    assert data["version"] == 1 and data["votes"][key][dest]["count"] == 1


@pytest.mark.parametrize("value,expected", [("3", 3), ("1", 1), ("0", 2), ("-1", 2), ("x", 2), ("", 2)])
def test_threshold_from_config(value, expected):
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"] = {"learn_threshold": value}
    assert get_threshold(cfg) == expected
    assert get_threshold(configparser.ConfigParser()) == 2


# --- reordering suggestions ---------------------------------------------------

def base_suggestions(file_path):
    return [
        {"action": "move", "source": str(file_path), "destination": str(file_path.parent / "Documents" / file_path.name), "reason": "r1"},
        {"action": "move", "source": str(file_path), "destination": str(file_path.parent / "Reports" / file_path.name), "reason": "r2"},
        {"action": "keep", "source": str(file_path), "reason": "Keep file in current location"},
    ]


def trained(tmp_path, root, dest, times=2, ext="pdf"):
    L = make_learner(tmp_path)
    for i in range(times):
        L.vote(root / f"x{i}.{ext}", dest, [root])
    return L


def test_nothing_learned_nothing_changes(tmp_path, root):
    L = make_learner(tmp_path)
    f = root / "a.pdf"
    s = base_suggestions(f)
    assert L.apply(f, s, [root]) == s


def test_an_existing_suggestion_is_moved_to_the_top(tmp_path, root):
    reports = root / "Reports"
    reports.mkdir()
    L = trained(tmp_path, root, reports)
    f = root / "a.pdf"
    out = L.apply(f, base_suggestions(f), [root])
    assert [s["action"] for s in out] == ["move", "move", "keep"]
    assert Path(out[0]["destination"]).parent == reports
    assert out[0]["learned_count"] == 2 and "2 similar files" in out[0]["reason"]
    assert Path(out[1]["destination"]).parent.name == "Documents"
    assert "learned_count" not in out[1]


def test_a_new_folder_is_added_at_the_top(tmp_path, root):
    taxes = tmp_path / "Taxes"
    taxes.mkdir()
    L = trained(tmp_path, root, taxes)
    f = root / "a.pdf"
    out = L.apply(f, base_suggestions(f), [root])
    assert len(out) == 4
    assert Path(out[0]["destination"]) == taxes / "a.pdf"
    assert out[0]["source"] == str(f) and out[0]["action"] == "move"


def test_a_deleted_folder_is_not_brought_back(tmp_path, root):
    L = trained(tmp_path, root, tmp_path / "Gone")
    f = root / "a.pdf"
    assert L.apply(f, base_suggestions(f), [root]) == base_suggestions(f)


def test_usual_keep_moves_the_keep_option_to_the_top(tmp_path, root):
    L = trained(tmp_path, root, KEEP, times=3)
    f = root / "a.pdf"
    out = L.apply(f, base_suggestions(f), [root])
    assert out[0]["action"] == "keep" and out[0]["learned_count"] == 3
    assert [s["action"] for s in out] == ["keep", "move", "move"]


def test_apply_does_not_modify_its_input(tmp_path, root):
    reports = root / "Reports"
    reports.mkdir()
    L = trained(tmp_path, root, reports)
    f = root / "a.pdf"
    s = base_suggestions(f)
    L.apply(f, s, [root])
    assert s == base_suggestions(f)


def test_a_file_already_in_its_usual_folder_gets_no_move_suggestion(tmp_path, root):
    pdfs = root / "PDFs"
    pdfs.mkdir()
    L = trained(tmp_path, root, pdfs)
    f = pdfs / "a.pdf"  # same group (the watched root is Downloads), already in the usual folder
    assert L.apply(f, base_suggestions(f), [root]) == base_suggestions(f)


def test_folders_that_differ_only_in_case_count_as_one_choice(tmp_path, root, monkeypatch):
    import learning
    monkeypatch.setattr(learning, "_norm", lambda p: str(p).lower())  # what Windows does
    L = make_learner(tmp_path)
    L.vote(root / "a.pdf", tmp_path / "Docs", [root])
    L.vote(root / "b.pdf", tmp_path / "DOCS", [root])
    path, count = L.usual(root / "c.pdf", [root])
    assert count == 2
    assert path == str(tmp_path / "DOCS")  # shown the way you last wrote it
