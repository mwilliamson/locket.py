import time
import errno


__all__ = ["lock_file"]


try:
    import fcntl
except ImportError:
    raise ImportError("Platform not supported (failed to import fcntl)")
else:
    def _lock_file_blocking(fd):
        fcntl.flock(fd, fcntl.LOCK_EX)
        
    def _lock_file_non_blocking(fd):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except IOError as error:
            if error.errno in [errno.EACCES, errno.EAGAIN]:
                return False
            else:
                raise
        
    def _unlock_file(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)


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
            _lock_file_blocking(self._file)
        else:
            start_time = time.time()
            while True:
                success = _lock_file_non_blocking(self._file)
                if success:
                    return
                elif time.time() - start_time > self._timeout:
                    raise LockError("Couldn't lock {0}".format(self._path))
                else:
                    time.sleep(self._retry_period)
                    
    
    def release(self):
        _unlock_file(self._file)
        self._file.close()
        self._file = None
    
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, *args):
        return
