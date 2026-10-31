"""Safe file operations: no overwriting, a persistent undo log, and Trash.

This module has no GUI or Windows-only code, so it runs and is tested on any
OS (see tests/test_safemove.py).
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

DEFAULT_MAX_ENTRIES = 500


def unique_destination(destination):
    """Return `destination`, or `name (2).ext`, `name (3).ext`... if it is taken."""
    destination = Path(destination)
    if not destination.exists():
        return destination
    n = 2
    while True:
        candidate = destination.with_name(f"{destination.stem} ({n}){destination.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def safe_move(source, destination):
    """Move a file without overwriting anything and return the final path.

    Creates missing parent folders. If a file already sits at `destination`,
    the moved file gets a numbered name instead. Raises FileNotFoundError if
    `source` is gone.
    """
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise FileNotFoundError(f"File not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    final = unique_destination(destination)
    shutil.move(str(source), str(final))
    return final


def trash_file(path):
    """Send a file to the system Trash / Recycle Bin. Never deletes for good.

    Raises RuntimeError if the Send2Trash library is not installed, so the
    caller can tell the user instead of falling back to a permanent delete.
    """
    try:
        from send2trash import send2trash
    except ImportError:
        raise RuntimeError(
            "Send2Trash is not installed, so the file was not deleted. "
            "Run: pip install -r requirements.txt"
        )
    send2trash(str(path))


class UndoLog:
    """The last `max_entries` actions, kept in a JSON file so undo survives a
    restart. Each entry has: type, file_path, timestamp, details."""

    def __init__(self, path, max_entries=DEFAULT_MAX_ENTRIES):
        self.path = Path(path)
        self.max_entries = max_entries
        self.entries = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        entries = [e for e in data if isinstance(e, dict) and "type" in e and "file_path" in e]
        return entries[-self.max_entries:]

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.entries, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as e:
            print(f"Error saving undo log: {e}")

    def __len__(self):
        return len(self.entries)

    def record(self, action_type, file_path, details=None):
        entry = {
            "type": action_type,
            "file_path": str(file_path),
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        self.entries.append(entry)
        del self.entries[:-self.max_entries]
        self._save()
        return entry

    def pop_last(self):
        """Remove and return the newest entry, or None if the log is empty."""
        if not self.entries:
            return None
        entry = self.entries.pop()
        self._save()
        return entry


def undo_move(entry):
    """Put a moved file back where it came from.

    Returns (ok, message, restored_path). Never overwrites: if something now
    sits at the original path, the file comes back under a numbered name.
    """
    current = Path(entry["file_path"])
    original = Path(entry["details"]["original_path"])
    if not current.exists():
        return False, f"File not found: {current}", None
    restored = safe_move(current, original)
    if restored != original:
        note = f" (as {restored.name}, because {original.name} already exists there)"
    else:
        note = ""
    return True, f"Undid move: {current.name} moved back to {restored.parent}{note}", restored
