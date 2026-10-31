import configparser
from types import SimpleNamespace

import pytest

pytest.importorskip("watchdog")

from file_monitor import FileChangeHandler, FileMonitor, is_ready_to_queue  # noqa: E402
from filewatch import SettleTracker  # noqa: E402


class FakeTracker:
    def __init__(self):
        self.watched = []

    def watch(self, path):
        self.watched.append(path)


class FakeIndexer:
    def __init__(self, settle=None):
        self.config = configparser.ConfigParser()
        if settle is not None:
            self.config["DEFAULT"] = {"settle_seconds": str(settle)}
        self.queued = []

    def add_to_suggestions_queue(self, path):
        self.queued.append(path)


def created(path, is_directory=False):
    return SimpleNamespace(is_directory=is_directory, src_path=str(path))


def moved(dest, is_directory=False):
    return SimpleNamespace(is_directory=is_directory, src_path="old", dest_path=str(dest))


@pytest.fixture
def handler():
    tracker = FakeTracker()
    return FileChangeHandler(FakeIndexer(), tracker), tracker


def test_new_file_is_watched_not_queued(handler):
    h, tracker = handler
    h.on_created(created("/dl/report.pdf"))
    assert tracker.watched == ["/dl/report.pdf"]
    assert h.indexer.queued == []


@pytest.mark.parametrize("name", ["a.zip.crdownload", "b.iso.part", "c.pdf.download", "d.tmp"])
def test_partial_downloads_are_ignored(handler, name):
    h, tracker = handler
    h.on_created(created(f"/dl/{name}"))
    assert tracker.watched == []


def test_download_finishing_with_a_rename_is_watched(handler):
    h, tracker = handler
    h.on_moved(moved("/dl/a.zip"))
    assert tracker.watched == ["/dl/a.zip"]


def test_rename_to_a_partial_name_is_ignored(handler):
    h, tracker = handler
    h.on_moved(moved("/dl/a.zip.part"))
    assert tracker.watched == []


def test_directories_and_ignored_folders_are_ignored(handler):
    h, tracker = handler
    h.on_created(created("/dl/folder", is_directory=True))
    h.on_created(created("/proj/.git/config.txt"))
    h.on_created(created("/dl/debug.log"))
    assert tracker.watched == []


def test_tiny_files_are_not_dropped_at_event_time(handler):
    # A download starts at 0 bytes; the size check now happens after it settles.
    h, tracker = handler
    h.on_created(created("/dl/growing.mp4"))
    assert tracker.watched == ["/dl/growing.mp4"]


def test_is_ready_to_queue(tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 2048)
    small = tmp_path / "small.bin"
    small.write_bytes(b"x")
    assert is_ready_to_queue(big)
    assert not is_ready_to_queue(small)
    assert not is_ready_to_queue(tmp_path)
    assert not is_ready_to_queue(tmp_path / "gone")


def test_settle_time_comes_from_the_config():
    assert FileMonitor(FakeIndexer(settle=12)).settle.quiet_seconds == 12
    assert FileMonitor(FakeIndexer()).settle.quiet_seconds == 5.0


def test_only_settled_and_big_enough_files_are_queued(tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 2048)
    small = tmp_path / "small.bin"
    small.write_bytes(b"x")
    indexer = FakeIndexer()
    monitor = FileMonitor(indexer)
    now = [0.0]
    monitor.settle = SettleTracker(quiet_seconds=5, clock=lambda: now[0])
    monitor.settle.watch(big)
    monitor.settle.watch(small)

    monitor.process_settled()
    assert indexer.queued == []  # nothing has been quiet long enough

    now[0] = 5
    monitor.process_settled()
    assert indexer.queued == [str(big)]

    monitor.process_settled()
    assert indexer.queued == [str(big)]  # not queued twice
