"""File system utilities for twin-mind."""

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, TextIO

from twin_mind.constants import (
    BRAIN_DIR,
    CODE_FILE,
    DECISIONS_MV2_FILE,
    ENTITIES_DB_FILE,
    GITIGNORE_CONTENT,
    GITIGNORE_FILE,
    MEMORY_FILE,
)

# File locking (platform-specific)
if sys.platform == "win32":
    import msvcrt

    def _lock_file(f: TextIO) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f: TextIO) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(f: TextIO) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_file(f: TextIO) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class FileLock:
    """Simple file-based lock with timeout."""

    def __init__(self, path: Path, timeout: int = 5) -> None:
        self.lock_path = Path(str(path) + ".lock")
        self.timeout = timeout
        self._lock_file: Optional[TextIO] = None

    def acquire(self) -> bool:
        """Acquire lock, return True if successful."""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # Check for stale lock (>60s old)
                if self.lock_path.exists():
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > 60:
                        self.lock_path.unlink()

                self._lock_file = open(self.lock_path, "w")
                _lock_file(self._lock_file)
                self._lock_file.write(str(os.getpid()))
                self._lock_file.flush()
                return True
            except OSError:
                time.sleep(0.1)
        return False

    def release(self) -> None:
        """Release the lock."""
        if self._lock_file:
            try:
                _unlock_file(self._lock_file)
                self._lock_file.close()
                if self.lock_path.exists():
                    self.lock_path.unlink()
            except OSError:
                pass
            self._lock_file = None

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise OSError(f"Could not acquire lock on {self.lock_path} (timeout {self.timeout}s)")
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()


def get_brain_dir() -> Path:
    """Get the .claude directory path."""
    return Path.cwd() / BRAIN_DIR


def get_code_path() -> Path:
    """Get the code store path."""
    return get_brain_dir() / CODE_FILE


def get_memory_path() -> Path:
    """Get the memory store path."""
    return get_brain_dir() / MEMORY_FILE


def get_decisions_path() -> Path:
    """Get path to shared decisions file (JSONL format)."""
    return get_brain_dir() / "decisions.jsonl"


def get_decisions_mv2_path() -> Path:
    """Get path to semantic index for shared decisions (regeneratable from JSONL)."""
    return get_brain_dir() / DECISIONS_MV2_FILE


def get_entities_db_path() -> Path:
    """Get path to entities graph SQLite database."""
    return get_brain_dir() / ENTITIES_DB_FILE


def ensure_brain_dir() -> None:
    """Create the brain directory if it doesn't exist."""
    get_brain_dir().mkdir(parents=True, exist_ok=True)


def create_gitignore() -> bool:
    """Create .gitignore in .claude directory. Returns True if created."""
    gitignore_path = get_brain_dir() / GITIGNORE_FILE
    if not gitignore_path.exists():
        gitignore_path.write_text(GITIGNORE_CONTENT)
        return True
    return False
