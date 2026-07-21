"""FileLock regression tests for the test-machine lock livelock (2026-07-21).

A killed app left registry.lock behind; every later registry write then stalled
for stale_timeout (300s) looking like a silent crash-exit, and concurrent
instances made the stale-break unlink fail with WinError 32, poisoning the lock
again. These tests pin the fixes: dead-PID locks break immediately, release
retries transient unlink failures, and the stale-break never steals a lock that
another process just refreshed.
"""

import os
import time

import pytest

from viu_media.core.utils.file import FileLock, _pid_alive


def write_lock(path, pid, timestamp):
    path.write_text(f"{pid}\n{timestamp}")


def test_pid_alive_self_and_dead():
    assert _pid_alive(os.getpid()) is True
    # PIDs are recycled, but 2**22 + odd offset is practically never in use.
    assert _pid_alive(4_194_301) is False
    assert _pid_alive(-1) is False


def test_dead_pid_lock_breaks_immediately(tmp_path):
    lock_path = tmp_path / "registry.lock"
    write_lock(lock_path, 4_194_301, time.time())  # fresh timestamp, dead owner

    lock = FileLock(lock_path, timeout=5, stale_timeout=300)
    start = time.time()
    lock.acquire()
    elapsed = time.time() - start

    assert lock._acquired is True
    # The whole point of the fix: no 300s stall when the owner is dead.
    assert elapsed < 2
    lock.release()
    assert not lock_path.exists()


def test_live_pid_fresh_lock_is_not_stolen(tmp_path):
    lock_path = tmp_path / "registry.lock"
    write_lock(lock_path, os.getpid(), time.time())  # live owner, fresh

    lock = FileLock(lock_path, timeout=0.5, stale_timeout=300)
    with pytest.raises(TimeoutError):
        lock.acquire()
    assert lock_path.exists()


def test_live_pid_age_stale_lock_still_breaks(tmp_path):
    lock_path = tmp_path / "registry.lock"
    write_lock(lock_path, os.getpid(), time.time() - 1000)  # live owner, ancient

    lock = FileLock(lock_path, timeout=5, stale_timeout=300)
    lock.acquire()
    assert lock._acquired is True
    lock.release()


def test_corrupt_lock_is_stale(tmp_path):
    lock_path = tmp_path / "registry.lock"
    lock_path.write_text("garbage")

    lock = FileLock(lock_path, timeout=5, stale_timeout=300)
    start = time.time()
    lock.acquire()
    assert time.time() - start < 2
    lock.release()


def test_release_retries_transient_unlink_failure(tmp_path, monkeypatch):
    lock_path = tmp_path / "registry.lock"
    lock = FileLock(lock_path, timeout=5, stale_timeout=300)
    lock.acquire()

    # Simulate WinError 32: the first two unlink attempts collide with another
    # process's read poll, then succeed.
    real_unlink = type(lock_path).unlink
    calls = {"n": 0}

    def flaky_unlink(self, missing_ok=False):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise OSError(32, "The process cannot access the file")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(type(lock_path), "unlink", flaky_unlink)
    lock.release()

    assert calls["n"] == 3
    assert not lock_path.exists()
    assert lock._acquired is False


def test_release_gives_up_but_clears_acquired(tmp_path, monkeypatch):
    lock_path = tmp_path / "registry.lock"
    lock = FileLock(lock_path, timeout=5, stale_timeout=300)
    lock.acquire()

    monkeypatch.setattr(FileLock, "_unlink_with_retry", lambda self: False)
    lock.release()
    # Even when the file can't be deleted, the lock object must not think it
    # still holds the lock.
    assert lock._acquired is False


def test_stale_break_skips_lock_refreshed_by_another_process(tmp_path, monkeypatch):
    """If the lock content changes to a live/fresh owner between the staleness
    check and the unlink, the break must be aborted (no lock stealing)."""
    lock_path = tmp_path / "registry.lock"
    write_lock(lock_path, 4_194_301, time.time())  # dead owner: looks stale

    lock = FileLock(lock_path, timeout=0.5, stale_timeout=300)

    # After the initial _is_stale() verdict, another process replaces the lock
    # with its own live, fresh one before our re-read.
    original_read = FileLock._read_lock_info
    state = {"first": True}

    def racing_read(self):
        info = original_read(self)
        if not state["first"]:
            return info
        state["first"] = False
        write_lock(lock_path, os.getpid(), time.time())
        return original_read(self)

    monkeypatch.setattr(FileLock, "_read_lock_info", racing_read)

    with pytest.raises(TimeoutError):
        lock.acquire()
    # The other process's lock survived.
    assert lock_path.exists()
    pid, _ = original_read(lock)
    assert pid == os.getpid()
