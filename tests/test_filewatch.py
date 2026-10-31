import os
import time

import pytest

from filewatch import SettleTracker, is_partial_name, is_still_changing, snapshot


@pytest.mark.parametrize("name", [
    "movie.mp4.crdownload", "setup.exe.part", "photo.jpg.download", "x.tmp", "X.CRDOWNLOAD",
])
def test_partial_names_are_detected(name):
    assert is_partial_name(name)


@pytest.mark.parametrize("name", ["movie.mp4", "notes.txt", "part", "crdownload", "a.part.pdf"])
def test_finished_names_are_not_partial(name):
    assert not is_partial_name(name)


def test_snapshot_of_missing_file_is_none(tmp_path):
    assert snapshot(tmp_path / "nope") is None


def test_snapshot_changes_when_the_file_grows(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    before = snapshot(f)
    f.write_bytes(b"xx")
    assert snapshot(f) != before


def set_age(path, seconds_old):
    t = time.time() - seconds_old
    os.utime(path, (t, t))


def test_recently_modified_file_is_still_changing(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    set_age(f, 1)
    assert is_still_changing(f, quiet_seconds=5)


def test_old_file_is_not_changing(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    set_age(f, 60)
    assert not is_still_changing(f, quiet_seconds=5)


def test_missing_file_is_not_reported_as_changing(tmp_path):
    assert not is_still_changing(tmp_path / "nope", quiet_seconds=5)


def test_quiet_period_boundary(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    set_age(f, 10)
    mtime = os.stat(f).st_mtime
    assert is_still_changing(f, quiet_seconds=5, now=mtime + 4.9)
    assert not is_still_changing(f, quiet_seconds=5, now=mtime + 5.0)


class Fake:
    """A scripted clock and a scripted file system for SettleTracker."""
    def __init__(self):
        self.now = 0.0
        self.snaps = {}

    def clock(self):
        return self.now

    def snap(self, path):
        return self.snaps.get(path)


@pytest.fixture
def fake():
    return Fake()


def tracker(fake, quiet=5.0):
    return SettleTracker(quiet_seconds=quiet, clock=fake.clock, snapshot_fn=fake.snap)


def test_unchanged_file_settles_after_the_quiet_period(fake):
    fake.snaps["a"] = (100, 1)
    t = tracker(fake)
    t.watch("a")
    fake.now = 4.9
    assert t.poll() == []
    fake.now = 5.0
    assert t.poll() == ["a"]
    assert len(t) == 0
    assert t.poll() == []  # released only once


def test_growing_file_keeps_waiting(fake):
    fake.snaps["a"] = (100, 1)
    t = tracker(fake)
    t.watch("a")
    fake.now = 4
    fake.snaps["a"] = (200, 2)  # still being written
    assert t.poll() == []
    fake.now = 8.9
    assert t.poll() == []  # only 4.9 s since the last change
    fake.now = 9.0
    assert t.poll() == ["a"]


def test_a_paused_download_longer_than_the_quiet_period_is_released(fake):
    # Known limit of the size/time check; the move itself re-checks the mtime.
    fake.snaps["a"] = (100, 1)
    t = tracker(fake)
    t.watch("a")
    fake.now = 30
    assert t.poll() == ["a"]


def test_vanished_file_is_dropped(fake):
    fake.snaps["a"] = (100, 1)
    t = tracker(fake)
    t.watch("a")
    del fake.snaps["a"]
    fake.now = 1
    assert t.poll() == []
    assert len(t) == 0


def test_file_not_visible_yet_gets_the_quiet_period_then_is_dropped(fake):
    t = tracker(fake)
    t.watch("a")  # no snapshot yet
    fake.now = 2
    assert t.poll() == []
    assert len(t) == 1
    fake.now = 5
    assert t.poll() == []
    assert len(t) == 0


def test_file_that_appears_late_settles_normally(fake):
    t = tracker(fake)
    t.watch("a")
    fake.now = 2
    fake.snaps["a"] = (50, 1)
    assert t.poll() == []
    fake.now = 7
    assert t.poll() == ["a"]


def test_watching_again_restarts_the_wait(fake):
    fake.snaps["a"] = (100, 1)
    t = tracker(fake)
    t.watch("a")
    fake.now = 4
    t.watch("a")
    fake.now = 8
    assert t.poll() == []
    fake.now = 9
    assert t.poll() == ["a"]


def test_files_are_tracked_independently(fake):
    fake.snaps.update({"a": (1, 1), "b": (1, 1)})
    t = tracker(fake)
    t.watch("a")
    fake.now = 3
    t.watch("b")
    fake.now = 5
    assert t.poll() == ["a"]
    fake.now = 8
    assert t.poll() == ["b"]


def test_works_with_real_files(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 10)
    now = [0.0]
    t = SettleTracker(quiet_seconds=2, clock=lambda: now[0])
    t.watch(f)
    now[0] = 1
    f.write_bytes(b"x" * 20)
    assert t.poll() == []
    now[0] = 3.5
    assert t.poll() == [str(f)]
