import fcntl
import time


__all__ = ["lock_file"]


def lock_file(*args, **kwargs):
    return _LockFile(*args, **kwargs)


class LockError(Exception):
    pass
    
    
class _LockFile(object):
    def __init__(self, path, timeout=None, retry_period=0.05):
        self._path = path
        self._timeout = timeout
        self._retry_period = retry_period
    
    def acquire(self):
        self._file = open(self._path, "w")
        if self._timeout is None:
            fcntl.flock(self._file, fcntl.LOCK_EX)
        else:
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except IOError:
                    if time.time() - start_time > self._timeout:
                        raise LockError("Couldn't lock {0}".format(self._path))
                    else:
                        time.sleep(self._retry_period)
                    
    
    def release(self):
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        self._file = None
    
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, *args):
        return
