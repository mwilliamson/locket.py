import contextlib
import tempfile
import shutil


@contextlib.contextmanager
def create_temporary_dir():
    try:
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

