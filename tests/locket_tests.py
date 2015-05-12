import functools
import os
import io
import sys
import time
import signal

from nose.tools import istest, nottest
import spur

import locket
from .tempdir import create_temporary_dir


local_shell = spur.LocalShell()


@nottest
def test(func):
    @functools.wraps(func)
    @istest
    def run_test():
        with create_temporary_dir() as temp_dir:
            lock_path = os.path.join(temp_dir, "some-lock")
            return func(lock_path)
        
    return run_test


@test
def single_process_can_obtain_uncontested_lock(lock_path):
    has_run = False
    with locket.lock_file(lock_path):
        has_run = True
    
    assert has_run


@test
def lock_can_be_acquired_with_timeout_of_zero(lock_path):
    has_run = False
    with locket.lock_file(lock_path, timeout=0):
        has_run = True
    
    assert has_run


@test
def lock_is_released_by_context_manager_exit(lock_path):
    has_run = False
    
    # Keep a reference to first_lock so it holds onto the lock
    first_lock = locket.lock_file(lock_path, timeout=0)
    
    with first_lock:
        pass
        
    with locket.lock_file(lock_path, timeout=0):
        has_run = True
    
    assert has_run


@test
def can_use_acquire_and_release_to_control_lock(lock_path):
    has_run = False
    lock = locket.lock_file(lock_path)
    lock.acquire()
    try:
        has_run = True
    finally:
        lock.release()
    
    assert has_run


@test
def thread_cannot_obtain_lock_using_same_object_twice_without_release(lock_path):
    with locket.lock_file(lock_path, timeout=0) as lock:
        try:
            lock.acquire()
            assert False, "Expected LockError"
        except locket.LockError:
            pass


@test
def thread_cannot_obtain_lock_using_same_path_twice_without_release(lock_path):
    with locket.lock_file(lock_path, timeout=0):
        lock = locket.lock_file(lock_path, timeout=0)
        try:
            lock.acquire()
            assert False, "Expected LockError"
        except locket.LockError:
            pass


@test
def the_same_lock_file_object_is_used_for_the_same_path(lock_path):
    first_lock = locket.lock_file(lock_path, timeout=0)
    second_lock = locket.lock_file(lock_path, timeout=0)
    assert first_lock is second_lock


@test
def different_file_objects_are_used_for_different_paths(lock_path):
    first_lock = locket.lock_file(lock_path, timeout=0)
    second_lock = locket.lock_file(lock_path + "-2", timeout=0)
    assert first_lock is not second_lock
            

@test
def lock_file_blocks_until_lock_is_available(lock_path):
    locker_1 = Locker(lock_path)
    locker_2 = Locker(lock_path)
    
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


@test
def lock_is_released_if_holding_process_is_brutally_killed(lock_path):
    locker_1 = Locker(lock_path)
    locker_2 = Locker(lock_path)
    
    assert not locker_1.has_lock()
    assert not locker_2.has_lock()
    
    locker_1.acquire()
    time.sleep(0.1)
    locker_2.acquire()
    time.sleep(0.1)
    
    assert locker_1.has_lock()
    assert not locker_2.has_lock()
    
    locker_1.kill(signal.SIGKILL)
    time.sleep(0.1)
    
    assert locker_2.has_lock()


@test
def can_set_timeout_to_zero_to_raise_exception_if_lock_cannot_be_acquired(lock_path):
    locker_1 = Locker(lock_path)
    locker_2 = Locker(lock_path, timeout=0)
    
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


@test
def error_is_raised_after_timeout_has_expired(lock_path):
    locker_1 = Locker(lock_path)
    locker_2 = Locker(lock_path, timeout=0.5)
    
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


@test
def lock_is_acquired_if_available_before_timeout_expires(lock_path):
    locker_1 = Locker(lock_path)
    locker_2 = Locker(lock_path, timeout=2)
    
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


def _lockers(number_of_lockers, lock_path):
    return tuple(Locker(lock_path) for i in range(number_of_lockers))
    

class Locker(object):
    def __init__(self, path, timeout=None):
        self._stdout = io.BytesIO()
        self._stderr = io.BytesIO()
        self._process = local_shell.spawn(
            [sys.executable, _locker_script_path, path, str(timeout)],
            stdout=self._stdout,
            stderr=self._stderr,
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
    
    def kill(self, signal):
        pid = int(self._stdout_lines()[0].strip())
        os.kill(pid, signal)
    
    def _stdout_lines(self):
        output = self._stdout.getvalue().decode("ascii")
        return [line.strip() for line in output.split("\n")]

_locker_script_path = os.path.join(os.path.dirname(__file__), "locker.py")
