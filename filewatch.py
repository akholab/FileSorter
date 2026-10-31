"""Helpers that tell whether a file is still being written.

A download or copy can take a while, and moving a file mid-write corrupts it.
Two checks keep that from happening: `is_partial_name` skips the temporary
names browsers use while downloading, and `SettleTracker` only releases a file
once its size and modified time have stayed the same for a few seconds.

No GUI or Windows-only code, so this runs and is tested on any OS
(see tests/test_filewatch.py).
"""

import os
import threading
import time
from pathlib import Path

# Temporary names used while a download is in progress: Chrome/Edge
# (.crdownload), Firefox (.part), Safari (.download) and generic temp files.
PARTIAL_SUFFIXES = {".crdownload", ".part", ".download", ".tmp"}

DEFAULT_QUIET_SECONDS = 5.0


def is_partial_name(path):
    """True if the file name marks an unfinished download (e.g. a.zip.part)."""
    return Path(path).suffix.lower() in PARTIAL_SUFFIXES


def snapshot(path):
    """Return (size, modified time in ns) or None if the file is gone."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def get_settle_seconds(config):
    """Read `settle_seconds` from the config; a missing, bad or negative value
    falls back to the default instead of crashing or disabling the check."""
    try:
        value = config.getfloat('DEFAULT', 'settle_seconds', fallback=DEFAULT_QUIET_SECONDS)
    except ValueError:
        return DEFAULT_QUIET_SECONDS
    return value if value >= 0 else DEFAULT_QUIET_SECONDS


def is_still_changing(path, quiet_seconds=DEFAULT_QUIET_SECONDS, now=None):
    """True if the file was modified less than `quiet_seconds` ago.

    A modified time far in the future (clock skew, a network share) is not
    "changing", or the file could never be moved.

    A stateless re-check to run right before moving a file. A missing file is
    not "changing"; the move itself reports that.
    """
    snap = snapshot(path)
    if snap is None:
        return False
    now = time.time() if now is None else now
    age = now - snap[1] / 1e9
    return abs(age) < quiet_seconds


class SettleTracker:
    """Releases a file only after it has stayed unchanged for `quiet_seconds`.

    Call `watch(path)` when a file appears or is renamed in. Call `poll()` every
    second or so: it returns the paths that have now settled. A file that
    vanishes is dropped. Safe to call from several threads.
    """

    def __init__(self, quiet_seconds=DEFAULT_QUIET_SECONDS, clock=time.monotonic,
                 snapshot_fn=snapshot):
        self.quiet_seconds = quiet_seconds
        self._clock = clock
        self._snapshot = snapshot_fn
        self._pending = {}  # path -> [last snapshot, time it last changed]
        self._lock = threading.Lock()

    def __len__(self):
        with self._lock:
            return len(self._pending)

    def watch(self, path):
        """Start (or restart) waiting for `path` to settle."""
        path = str(path)
        with self._lock:
            self._pending[path] = [self._snapshot(path), self._clock()]

    def poll(self):
        """Return the paths that have settled, and stop tracking them."""
        with self._lock:
            items = [(path, entry) for path, entry in self._pending.items()]
        # Stat outside the lock: a slow or network drive must not block watch().
        snaps = {path: self._snapshot(path) for path, _ in items}
        settled = []
        with self._lock:
            now = self._clock()
            for path, entry in items:
                if self._pending.get(path) is not entry:
                    continue  # watched again (or removed) while we were checking
                last_snap, changed_at = entry
                snap = snaps[path]
                if snap is None:
                    if last_snap is None and now - changed_at < self.quiet_seconds:
                        continue  # not visible yet: give it the quiet period
                    del self._pending[path]  # gone
                    continue
                if snap != last_snap:
                    entry[0], entry[1] = snap, now
                elif now - changed_at >= self.quiet_seconds:
                    del self._pending[path]
                    settled.append(path)
        return settled
