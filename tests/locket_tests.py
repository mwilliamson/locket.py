import functools
import os
import io
import sys
import time
import signal

import pytest
import spur

import locket
from .tempdir import create_temporary_dir


local_shell = spur.LocalShell()


@pytest.fixture(name="lock_path")
def _fixture_lock_path():
    with create_temporary_dir() as temp_dir:
        yield os.path.join(temp_dir, "some-lock")


@pytest.fixture(name="spawn_locker")
def _fixture_spawn_locker():
    lockers = []

    def spawn_locker(*args, **kwargs):
        locker = _Locker(*args, **kwargs)
        lockers.append(locker)
        return locker

    try:
        yield spawn_locker
    finally:
        for locker in lockers:
            locker.terminate()
            locker.wait()


def test_single_process_can_obtain_uncontested_lock(lock_path):
    has_run = False
    with locket.lock_file(lock_path):
        has_run = True

    assert has_run


def test_lock_can_be_acquired_with_timeout_of_zero(lock_path):
    has_run = False
    with locket.lock_file(lock_path, timeout=0):
        has_run = True

    assert has_run


def test_lock_is_released_by_context_manager_exit(lock_path):
    has_run = False

    # Keep a reference to first_lock so it holds onto the lock
    first_lock = locket.lock_file(lock_path, timeout=0)

    with first_lock:
        pass

    with locket.lock_file(lock_path, timeout=0):
        has_run = True

    assert has_run


def test_can_use_acquire_and_release_to_control_lock(lock_path):
    has_run = False
    lock = locket.lock_file(lock_path)
    lock.acquire()
    try:
        has_run = True
    finally:
        lock.release()

    assert has_run


def test_thread_cannot_obtain_lock_using_same_object_twice_without_release(lock_path):
    with locket.lock_file(lock_path, timeout=0) as lock:
        try:
            lock.acquire()
            assert False, "Expected LockError"
        except locket.LockError:
            pass


def test_thread_cannot_obtain_lock_using_same_path_twice_without_release(lock_path):
    with locket.lock_file(lock_path, timeout=0):
        lock = locket.lock_file(lock_path, timeout=0)
        try:
            lock.acquire()
            assert False, "Expected LockError"
        except locket.LockError:
            pass


def test_thread_cannot_obtain_lock_using_same_path_with_different_arguments_without_release(lock_path):
    lock1 = locket.lock_file(lock_path, timeout=None)
    lock2 = locket.lock_file(lock_path, timeout=0)
    lock1.acquire()
    try:
        lock2.acquire()
        assert False, "Expected LockError"
    except locket.LockError:
        pass


def test_calling_release_on_unlocked_lock_raises_lock_error(lock_path):
    lock = locket.lock_file(lock_path)
    try:
        lock.release()
        assert False, "Expected LockError"
    except locket.LockError as error:
        assert str(error) == "cannot release unlocked lock"


def test_the_same_lock_file_object_is_used_for_the_same_path(lock_path):
    # We explicitly check the same lock is used to ensure that the lock isn't
    # re-entrant, even if the underlying platform lock is re-entrant.
    first_lock = locket.lock_file(lock_path, timeout=0)
    second_lock = locket.lock_file(lock_path, timeout=0)
    assert first_lock._lock is second_lock._lock


def test_the_same_lock_file_object_is_used_for_the_same_path_with_different_arguments(lock_path):
    # We explicitly check the same lock is used to ensure that the lock isn't
    # re-entrant, even if the underlying platform lock is re-entrant.
    first_lock = locket.lock_file(lock_path, timeout=None)
    second_lock = locket.lock_file(lock_path, timeout=0)
    assert first_lock._lock is second_lock._lock


def test_different_file_objects_are_used_for_different_paths(lock_path):
    first_lock = locket.lock_file(lock_path, timeout=0)
    second_lock = locket.lock_file(lock_path + "-2", timeout=0)
    assert first_lock._lock is not second_lock._lock


def test_lock_file_blocks_until_lock_is_available(lock_path, spawn_locker):
    locker_1 = spawn_locker(lock_path)
    locker_2 = spawn_locker(lock_path)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.release()
    time.sleep(0.1)

    assert not locker_1.has_lock()
    assert locker_2.has_lock()

    locker_2.release()
    time.sleep(0.1)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()


def test_lock_is_released_if_holding_process_is_brutally_killed(lock_path, spawn_locker):
    locker_1 = spawn_locker(lock_path)
    locker_2 = spawn_locker(lock_path)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.terminate()
    time.sleep(0.1)

    assert locker_2.has_lock()
    locker_2.release()


def test_can_set_timeout_to_zero_to_raise_exception_if_lock_cannot_be_acquired(lock_path, spawn_locker):
    locker_1 = spawn_locker(lock_path)
    locker_2 = spawn_locker(lock_path, timeout=0)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.release()
    time.sleep(0.1)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()
    assert locker_2.has_error()


def test_error_is_raised_after_timeout_has_expired(lock_path, spawn_locker):
    locker_1 = spawn_locker(lock_path)
    locker_2 = spawn_locker(lock_path, timeout=0.5)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()
    assert not locker_2.has_error()

    time.sleep(1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()
    assert locker_2.has_error()

    locker_1.release()


def test_lock_is_acquired_if_available_before_timeout_expires(lock_path, spawn_locker):
    locker_1 = spawn_locker(lock_path)
    locker_2 = spawn_locker(lock_path, timeout=2)

    assert not locker_1.has_lock()
    assert not locker_2.has_lock()

    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)

    assert locker_1.has_lock()
    assert not locker_2.has_lock()
    assert not locker_2.has_error()

    time.sleep(0.5)
    locker_1.release()
    time.sleep(0.1)

    assert not locker_1.has_lock()
    assert locker_2.has_lock()

    locker_2.release()



class _Locker(object):
    def __init__(self, path, timeout=None):
        self._stdout = io.BytesIO()
        self._stderr = io.BytesIO()
        self._process = local_shell.spawn(
            [sys.executable, _locker_script_path, path, str(timeout)],
            stdout=self._stdout,
            stderr=self._stderr,
            allow_error=True,
        )

    def acquire(self):
        self._process.stdin_write(b"\n")

    def release(self):
        self._process.stdin_write(b"\n")

    def wait_for_lock(self):
        start_time = time.time()
        while not self.has_lock():
            if not self._process.is_running():
                raise self._process.wait_for_result().to_error()
            time.sleep(0.1)
            if time.time() - start_time > 1:
                raise RuntimeError("Could not acquire lock, stdout:\n{0}".format(self._stdout.getvalue()))

    def has_lock(self):
        lines = self._stdout_lines()
        return "Acquired" in lines and "Released" not in lines

    def has_error(self):
        return "LockError" in self._stdout_lines()

    def terminate(self):
        pid = int(self._stdout_lines()[0].strip())
        os.kill(pid, getattr(signal, "SIGKILL", 9))

    def wait(self):
        self._process.wait_for_result()

    def _stdout_lines(self):
        output = self._stdout.getvalue().decode("ascii")
        return [line.strip() for line in output.split("\n")]

_locker_script_path = os.path.join(os.path.dirname(__file__), "locker.py")
