"""Learns where you usually put files, from the moves you make.

Every move you approve (or make by hand) is a vote for the destination folder,
and every "Keep" is a vote for leaving the file where it is. Votes are grouped
by *extension + watched folder* (".pdf in Downloads"). Once the same choice has
been made `threshold` times (default 2) and it is the most-voted choice for
that group, it goes to the top of the suggestions. A "Skip" teaches nothing.

The votes are saved to a JSON file so they survive a restart. No GUI or
Windows-only code; tested in tests/test_learning.py.
"""

import copy
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

DEFAULT_THRESHOLD = 2
KEEP = ""  # the "destination" that stands for "leave the file where it is"


def _norm(path):
    return os.path.normcase(str(path))


def get_threshold(config):
    """Read `learn_threshold` from the config; a bad value falls back to 2."""
    try:
        value = config.getint('DEFAULT', 'learn_threshold', fallback=DEFAULT_THRESHOLD)
    except ValueError:
        return DEFAULT_THRESHOLD
    return value if value >= 1 else DEFAULT_THRESHOLD


class Learner:
    def __init__(self, path, threshold=DEFAULT_THRESHOLD):
        self.path = Path(path)
        self.threshold = threshold
        self._lock = threading.RLock()
        # {group key: {destination folder or KEEP: {"count": n, "last": iso time}}}
        self.votes = self._load()

    # --- grouping -----------------------------------------------------------

    @staticmethod
    def key_for(file_path, roots=()):
        """The group a file belongs to: its extension plus the watched folder
        that contains it (or its own folder if it is not under a watched one)."""
        file_path = Path(file_path)
        folder = file_path.parent
        best = None
        for root in roots:
            root_n = _norm(root).rstrip("\\/")
            here = _norm(file_path.parent).rstrip("\\/")
            if here == root_n or here.startswith(root_n + os.sep) or here.startswith(root_n + "/"):
                if best is None or len(root_n) > len(best[0]):
                    best = (root_n, root)
        if best is not None:
            folder = best[1]
        return f"{file_path.suffix.lower()}|{_norm(folder)}"

    # --- storage ------------------------------------------------------------

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        votes = data.get("votes") if isinstance(data, dict) else None
        if not isinstance(votes, dict):
            return {}
        clean = {}
        for key, dests in votes.items():
            if not isinstance(dests, dict):
                continue
            for dest, info in dests.items():
                if isinstance(info, dict) and isinstance(info.get("count"), int) and info["count"] > 0:
                    clean.setdefault(key, {})[dest] = {"count": info["count"], "last": str(info.get("last", ""))}
        return clean

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"version": 1, "votes": self.votes}, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as e:
            print(f"Error saving learned choices: {e}")

    # --- voting -------------------------------------------------------------

    def vote(self, file_path, destination_folder, roots=()):
        """Count one vote. `destination_folder` is a folder path, or KEEP.
        Returns (key, destination) so the vote can be retracted on undo."""
        key = self.key_for(file_path, roots)
        dest = KEEP if destination_folder == KEEP else str(Path(destination_folder))
        self.add(key, dest)
        return key, dest

    def add(self, key, dest):
        with self._lock:
            entry = self.votes.setdefault(key, {}).setdefault(dest, {"count": 0, "last": ""})
            entry["count"] += 1
            entry["last"] = datetime.now().isoformat()
            self._save()

    def retract(self, key, dest):
        """Take back one vote (used when the user undoes the move)."""
        with self._lock:
            entry = self.votes.get(key, {}).get(dest)
            if not entry:
                return
            entry["count"] -= 1
            if entry["count"] <= 0:
                del self.votes[key][dest]
                if not self.votes[key]:
                    del self.votes[key]
            self._save()

    # --- using the votes ----------------------------------------------------

    def usual(self, file_path, roots=()):
        """Return (destination or KEEP, vote count) if one choice has earned
        the top spot, else None. The choice must have at least `threshold`
        votes and be the most-voted one; on a tie the most recent wins."""
        key = self.key_for(file_path, roots)
        with self._lock:
            dests = self.votes.get(key)
            if not dests:
                return None
            dest, info = max(dests.items(), key=lambda kv: (kv[1]["count"], kv[1]["last"]))
            if info["count"] < self.threshold:
                return None
            return dest, info["count"]

    def apply(self, file_path, suggestions, roots=()):
        """Return `suggestions` with the learned choice moved (or added) at the
        top, tagged with `learned_count`. Unchanged if nothing has been learned."""
        usual = self.usual(file_path, roots)
        if usual is None:
            return suggestions
        dest, count = usual
        file_path = Path(file_path)
        suggestions = copy.deepcopy(suggestions)

        if dest == KEEP:
            for i, s in enumerate(suggestions):
                if s["action"] == "keep":
                    s["learned_count"] = count
                    s["reason"] = f"You usually keep these here ({count} times)"
                    return [suggestions.pop(i)] + suggestions
            return suggestions

        if not Path(dest).is_dir():
            return suggestions  # the folder was deleted: don't bring it back

        wanted = _norm(dest)
        for i, s in enumerate(suggestions):
            if s["action"] == "move" and _norm(Path(s["destination"]).parent) == wanted:
                s["learned_count"] = count
                s["reason"] = f"You moved {count} similar files here"
                return [suggestions.pop(i)] + suggestions
        learned = {
            "action": "move",
            "source": str(file_path),
            "destination": str(Path(dest) / file_path.name),
            "reason": f"You moved {count} similar files here",
            "learned_count": count,
        }
        return [learned] + suggestions
