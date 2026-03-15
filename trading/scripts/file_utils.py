"""Shared file I/O utilities with process-safe locking."""

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


def append_jsonl(path: Path, record: Any) -> None:
    """Append a single JSON record to a JSONL file with an exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(record) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def job_lock(job_name: str, lock_dir: Path) -> Generator[bool, None, None]:
    """Context manager that prevents double-execution of a named job.

    Writes a PID lock file under lock_dir/<job_name>.lock.  If the lock file
    exists and the recorded PID is still alive, yields False (caller should
    skip).  Otherwise acquires the lock, yields True, and removes the lock on
    exit (even on exceptions).

    Usage::

        with job_lock("execute_longs", TRADING_DIR / ".pids") as acquired:
            if not acquired:
                logger.warning("execute_longs already running, skipping.")
                return
            # ... run the job ...
    """
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"{job_name}.lock"
    acquired = False
    try:
        if lock_file.exists():
            try:
                pid = int(lock_file.read_text().strip())
                os.kill(pid, 0)
                yield False
                return
            except (ValueError, OSError):
                pass
        lock_file.write_text(str(os.getpid()))
        acquired = True
        yield True
    finally:
        if acquired and lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass
