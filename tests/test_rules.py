"""Tests for rules.py: reading and writing rules.toml. Every test uses a temp
folder, never a real rules file."""
import pytest

import rules
from categorizer import DEFAULT_CATEGORIES, categorize_file


def test_default_text_round_trips_to_the_built_in_categories():
    assert rules.parse(rules.default_text()) == DEFAULT_CATEGORIES
    assert list(rules.parse(rules.default_text())) == list(DEFAULT_CATEGORIES)


def test_missing_file_is_written_with_defaults_and_comments(tmp_path):
    path = tmp_path / "rules.toml"
    categories, error = rules.load(str(path))
    assert error is None
    assert categories == DEFAULT_CATEGORIES
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# FileSorter rules.")
    assert rules.load(str(path)) == (DEFAULT_CATEGORIES, None)


def test_edited_file_is_used(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_text(
        '# my rules\n'
        '[categories.taxes]\n'
        'extensions = ["PDF", "xlsx"]\n'
        'keywords = ["Invoice"]\n'
        'folders = ["Taxes"]\n',
        encoding="utf-8",
    )
    categories, error = rules.load(str(path))
    assert error is None
    assert categories == {"taxes": {"extensions": [".pdf", ".xlsx"], "keywords": ["invoice"], "folders": ["Taxes"]}}
    assert categorize_file("C:/x/report.PDF", categories) == "taxes"
    assert categorize_file("C:/x/invoice-may.zip", categories) == "taxes"


def test_category_order_is_kept_so_the_first_match_wins(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_text(
        '[categories.first]\nextensions = [".pdf"]\nfolders = ["A"]\n'
        '[categories.second]\nextensions = [".pdf"]\nfolders = ["B"]\n',
        encoding="utf-8",
    )
    categories, _ = rules.load(str(path))
    assert list(categories) == ["first", "second"]
    assert categorize_file("x.pdf", categories) == "first"


def test_syntax_error_falls_back_to_defaults_and_names_the_line(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_text('[categories.docs]\nextensions = [".pdf"\nfolders = ["Docs"]\n', encoding="utf-8")
    categories, error = rules.load(str(path))
    assert categories == DEFAULT_CATEGORIES
    assert "line" in error and "rules.toml" in error
    assert path.read_text(encoding="utf-8").startswith("[categories.docs]")  # the user's file is left alone


@pytest.mark.parametrize("text, words", [
    ('title = "no categories"\n', "no [categories"),
    ('[categories.docs]\nextensions = ".pdf"\nfolders = ["Docs"]\n', "extensions must be a list"),
    ('[categories.docs]\nextensions = [1]\nfolders = ["Docs"]\n', "extensions must be a list"),
    ('[categories.docs]\nextensions = [".pdf"]\nfolders = []\n', "needs at least one folder"),
    ('[categories]\ndocs = "x"\n', "must be a [categories.docs] block"),
])
def test_wrong_shapes_fall_back_with_a_reason(tmp_path, text, words):
    path = tmp_path / "rules.toml"
    path.write_text(text, encoding="utf-8")
    categories, error = rules.load(str(path))
    assert categories == DEFAULT_CATEGORIES
    assert words in error


def test_missing_keywords_list_is_allowed(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_text('[categories.docs]\nextensions = [".pdf"]\nfolders = ["Docs"]\n', encoding="utf-8")
    categories, error = rules.load(str(path))
    assert error is None
    assert categories["docs"]["keywords"] == []


def test_unreadable_file_falls_back(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_bytes(b"\xff\xfe not utf-8")
    categories, error = rules.load(str(path))
    assert categories == DEFAULT_CATEGORIES
    assert error


def test_returned_defaults_are_a_copy(tmp_path):
    categories, _ = rules.load(str(tmp_path / "rules.toml"))
    categories["documents"]["folders"].append("X")
    assert "X" not in DEFAULT_CATEGORIES["documents"]["folders"]
