from pathlib import Path

import pytest

from categorizer import (
    DEFAULT_CATEGORIES,
    categorize_file,
    default_categories,
    describe_top,
    suggest_organization,
)

CATS = DEFAULT_CATEGORIES


@pytest.mark.parametrize("name,expected", [
    ("report.pdf", "documents"),
    ("notes.TXT", "documents"),
    ("holiday.jpg", "images"),
    ("clip.mkv", "videos"),
    ("song.flac", "audio"),
    ("data.zip", "archives"),
    ("tool.py", "code"),
])
def test_extension_decides_category(name, expected):
    assert categorize_file(name, CATS) == expected


def test_extension_is_case_insensitive():
    assert categorize_file("PHOTO.JPG", CATS) == "images"


def test_extension_wins_over_keyword():
    # "music" is an audio keyword, but .pdf is a document extension.
    assert categorize_file("music.pdf", CATS) == "documents"


@pytest.mark.parametrize("name,expected", [
    ("my_screenshot.xyz", "images"),
    ("Backup-2026.dat", "archives"),
    ("podcast_ep1", "audio"),
])
def test_keyword_used_when_extension_unknown(name, expected):
    assert categorize_file(name, CATS) == expected


def test_keyword_only_checks_the_stem_not_the_extension():
    assert categorize_file("data.video", CATS) == "misc"


@pytest.mark.parametrize("name", ["data.xyz", "noextension", ".hidden"])
def test_unknown_files_are_misc(name):
    assert categorize_file(name, CATS) == "misc"


def test_full_path_works_like_a_name():
    assert categorize_file(Path("C:/Users/x/Downloads/a.png"), CATS) == "images"


def test_custom_categories_are_respected():
    cats = {"ebooks": {"extensions": [".epub"], "keywords": [], "folders": ["Books"]}}
    assert categorize_file("novel.epub", cats) == "ebooks"
    assert categorize_file("novel.pdf", cats) == "misc"


def test_first_matching_category_wins_in_order():
    cats = {
        "a": {"extensions": [".x"], "keywords": [], "folders": ["A"]},
        "b": {"extensions": [".x"], "keywords": [], "folders": ["B"]},
    }
    assert categorize_file("f.x", cats) == "a"


def test_suggestions_list_every_folder_then_keep():
    src = Path("watch") / "photo.jpg"
    result = suggest_organization(src, CATS)
    moves = [s for s in result if s["action"] == "move"]
    assert [Path(m["destination"]).parent.name for m in moves] == ["Images", "Photos", "Screenshots"]
    assert all(Path(m["destination"]).name == "photo.jpg" for m in moves)
    assert all(Path(m["destination"]).parent.parent == src.parent for m in moves)
    assert all(m["source"] == str(src) for m in moves)
    assert result[-1]["action"] == "keep"
    assert result[-1]["source"] == str(src)


def test_misc_files_only_get_keep():
    result = suggest_organization("weird.xyz", CATS)
    assert [s["action"] for s in result] == ["keep"]


def test_default_categories_returns_an_independent_copy():
    a = default_categories()
    a["documents"]["extensions"].append(".zzz")
    assert ".zzz" not in default_categories()["documents"]["extensions"]
    assert ".zzz" not in DEFAULT_CATEGORIES["documents"]["extensions"]


def test_every_category_has_the_required_keys():
    for name, rules in DEFAULT_CATEGORIES.items():
        assert set(rules) == {"extensions", "keywords", "folders"}, name
        assert rules["folders"], name


def test_describe_top_names_the_category_for_a_category_move():
    s = [{"action": "move", "source": "C:/d/a.pdf", "destination": "C:/d/Documents/a.pdf"}, {"action": "keep"}]
    folder, reason = describe_top(s, "documents")
    assert Path(folder) == Path("C:/d/Documents")
    assert reason == "category: documents"


def test_describe_top_says_your_usual_without_a_count():
    s = [{"action": "move", "destination": "C:/Taxes/a.pdf", "learned_count": 4}, {"action": "keep"}]
    assert describe_top(s, "documents")[1] == "your usual"


def test_describe_top_for_keep():
    assert describe_top([{"action": "keep"}], "misc") == (None, "no category matched")
    assert describe_top([{"action": "keep", "learned_count": 2}], "documents") == (None, "your usual: keep it here")
    assert describe_top([], "misc") == (None, "no category matched")
