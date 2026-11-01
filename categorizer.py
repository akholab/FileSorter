"""Pure sorting logic: decides a category and suggests destinations.

This module has no GUI, Windows or filesystem-write code, so it imports and
runs on any OS and is covered by tests/test_categorizer.py.
"""

import copy
from pathlib import Path

DEFAULT_CATEGORIES = {
    "documents": {
        "extensions": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"],
        "keywords": ["document", "report", "contract", "proposal", "manual"],
        "folders": ["Documents", "Reports", "Contracts"]
    },
    "images": {
        "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"],
        "keywords": ["photo", "image", "picture", "screenshot"],
        "folders": ["Images", "Photos", "Screenshots"]
    },
    "videos": {
        "extensions": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv"],
        "keywords": ["video", "movie", "clip", "recording"],
        "folders": ["Videos", "Movies", "Recordings"]
    },
    "audio": {
        "extensions": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
        "keywords": ["audio", "music", "song", "podcast"],
        "folders": ["Audio", "Music", "Podcasts"]
    },
    "archives": {
        "extensions": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "keywords": ["archive", "backup", "compressed"],
        "folders": ["Archives", "Backups"]
    },
    "code": {
        "extensions": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".php"],
        "keywords": ["code", "script", "program", "source"],
        "folders": ["Code", "Scripts", "Projects"]
    }
}


def default_categories():
    """Return a fresh copy of the built-in categories (safe to modify)."""
    return copy.deepcopy(DEFAULT_CATEGORIES)


def categorize_file(file_path, categories):
    """Return the category name for a file: extension first, then filename
    keywords, otherwise "misc"."""
    try:
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        filename = file_path.stem.lower()

        for category, rules in categories.items():
            if extension in rules["extensions"]:
                return category

        for category, rules in categories.items():
            for keyword in rules["keywords"]:
                if keyword in filename:
                    return category

        return "misc"
    except (OSError, ValueError) as e:
        print(f"Error categorizing file {file_path}: {e}")
        return "misc"


def suggest_organization(file_path, categories):
    """Return the list of move suggestions for a file, ending with "keep"."""
    try:
        category = categorize_file(file_path, categories)
        file_path = Path(file_path)

        suggestions = []

        if category in categories:
            for folder in categories[category]["folders"]:
                target_dir = file_path.parent / folder
                suggestions.append({
                    "action": "move",
                    "source": str(file_path),
                    "destination": str(target_dir / file_path.name),
                    "reason": f"File appears to be {category} based on extension/content"
                })

        suggestions.append({
            "action": "keep",
            "source": str(file_path),
            "reason": "Keep file in current location"
        })

        return suggestions
    except (OSError, ValueError) as e:
        print(f"Error generating suggestions for {file_path}: {e}")
        return [{
            "action": "keep",
            "source": str(file_path),
            "reason": "Keep file in current location (categorization failed)"
        }]


def describe_top(suggestions, category):
    """Return (destination folder or None, reason) for the first suggestion,
    in words for the Preview list."""
    top = suggestions[0] if suggestions else {"action": "keep"}
    if top["action"] != "move":
        return None, "your usual: keep it here" if top.get("learned_count") else "no category matched"
    folder = str(Path(top["destination"]).parent)
    if top.get("learned_count"):
        return folder, "your usual"
    return folder, f"category: {category}"
