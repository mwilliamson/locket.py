# locket.py

```python
import locket

# Wait for lock
with locket.lock_file("path/to/lock/file"):
    perform_action()

# Raise error if lock cannot be acquired immediately
with locket.lock_file("path/to/lock/file", timeout=0):
    perform_action()
    
# Raise error if lock cannot be acquired after thirty seconds
with locket.lock_file("path/to/lock/file", timeout=30):
    perform_action()
    
# Without context managers:
lock = locket.lock_file("path/to/lock/file")
try:
    lock.acquire()
    perform_action()
finally:
    lock.release()
```
