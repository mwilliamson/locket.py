import time
import errno


__all__ = ["lock_file"]


try:
    import fcntl
except ImportError:
    try:
        import msvcrt
    except ImportError:
        raise ImportError("Platform not supported (failed to import fcntl, msvcrt)")
    else:
        _lock_file_blocking_available = False
    
        def _lock_file_non_blocking(file_):
            try:
                msvcrt.locking(file_.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            # TODO: check errno
            except IOError:
                return False
            
        def _unlock_file(file_):
            msvcrt.locking(file_.fileno(), msvcrt.LK_UNLCK, 1)
        
else:
    _lock_file_blocking_available = True
    def _lock_file_blocking(file_):
        fcntl.flock(file_.fileno(), fcntl.LOCK_EX)
        
    def _lock_file_non_blocking(file_):
        try:
            fcntl.flock(file_.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except IOError as error:
            if error.errno in [errno.EACCES, errno.EAGAIN]:
                return False
            else:
                raise
        
    def _unlock_file(file_):
        fcntl.flock(file_.fileno(), fcntl.LOCK_UN)


def lock_file(*args, **kwargs):
    return _LockFile(*args, **kwargs)


class LockError(Exception):
    pass
    
    
class _LockFile(object):
    def __init__(self, path, timeout=None, retry_period=0.05):
        self._path = path
        self._timeout = timeout
        self._retry_period = retry_period
        self._file = None
    
    def acquire(self):
        if self._file is None:
            self._file = open(self._path, "w")
        if self._timeout is None and _lock_file_blocking_available:
            _lock_file_blocking(self._file)
        else:
            start_time = time.time()
            while True:
                success = _lock_file_non_blocking(self._file)
                if success:
                    return
                elif (self._timeout is not None and
                        time.time() - start_time > self._timeout):
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
