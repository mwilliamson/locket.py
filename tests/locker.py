#!/usr/bin/env python

from __future__ import print_function

import sys
import os

import locket


def _print(output):
    print(output)
    sys.stdout.flush()


if __name__ == "__main__":
    print(os.getpid())
    lock_path = sys.argv[1]
    if sys.argv[2] == "None":
        timeout = None
    else:
        timeout = float(sys.argv[2])
    lock = locket.lock_file(lock_path, timeout=timeout)

    _print("Send newline to stdin to acquire")
    sys.stdin.readline()
    try:
        lock.acquire()
    except locket.LockError:
        _print("LockError")
        exit(1)
    _print("Acquired")

    _print("Send newline to stdin to release")
    sys.stdin.readline()
    lock.release()
    _print("Released")
