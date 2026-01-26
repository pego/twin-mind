"""Tests for twin_mind.fs module."""

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

from twin_mind.fs import (
    FileLock,
    create_gitignore,
    ensure_brain_dir,
    get_brain_dir,
    get_code_path,
    get_decisions_path,
    get_memory_path,
)


class TestFileLock:
    """Tests for FileLock class."""

    def test_acquire_and_release(self, temp_dir: Path) -> None:
        """Test acquiring and releasing a lock."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        lock = FileLock(test_file)
        assert lock.acquire() is True
        assert lock.lock_path.exists()
        lock.release()
        assert not lock.lock_path.exists()

    def test_context_manager(self, temp_dir: Path) -> None:
        """Test FileLock as context manager."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        with FileLock(test_file) as lock:
            assert lock.lock_path.exists()

        assert not lock.lock_path.exists()

    def test_lock_prevents_double_acquisition(self, temp_dir: Path) -> None:
        """Test that a lock prevents another process from acquiring it."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        lock1 = FileLock(test_file, timeout=1)
        lock2 = FileLock(test_file, timeout=1)

        assert lock1.acquire() is True
        # Lock2 should fail to acquire within timeout
        assert lock2.acquire() is False
        lock1.release()

    def test_stale_lock_cleanup(self, temp_dir: Path) -> None:
        """Test that stale locks are cleaned up."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        lock_path = Path(str(test_file) + ".lock")

        # Create a stale lock file (older than 60 seconds)
        lock_path.write_text("12345")
        # Set mtime to 70 seconds ago
        old_time = os.path.getmtime(lock_path) - 70
        os.utime(lock_path, (old_time, old_time))

        lock = FileLock(test_file)
        assert lock.acquire() is True
        lock.release()

    def test_context_manager_raises_on_timeout(self, temp_dir: Path) -> None:
        """Test that context manager raises IOError on timeout."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        lock1 = FileLock(test_file)
        lock1.acquire()

        with pytest.raises(IOError):
            with FileLock(test_file, timeout=1):
                pass

        lock1.release()


class TestPathFunctions:
    """Tests for path helper functions."""

    def test_get_brain_dir(self, temp_dir: Path) -> None:
        """Test get_brain_dir returns correct path."""
        brain_dir = get_brain_dir()
        assert brain_dir == temp_dir / ".claude"

    def test_get_code_path(self, temp_dir: Path) -> None:
        """Test get_code_path returns correct path."""
        code_path = get_code_path()
        assert code_path == temp_dir / ".claude" / "code.mv2"

    def test_get_memory_path(self, temp_dir: Path) -> None:
        """Test get_memory_path returns correct path."""
        memory_path = get_memory_path()
        assert memory_path == temp_dir / ".claude" / "memory.mv2"

    def test_get_decisions_path(self, temp_dir: Path) -> None:
        """Test get_decisions_path returns correct path."""
        decisions_path = get_decisions_path()
        assert decisions_path == temp_dir / ".claude" / "decisions.jsonl"


class TestEnsureBrainDir:
    """Tests for ensure_brain_dir function."""

    def test_creates_brain_dir(self, temp_dir: Path) -> None:
        """Test that ensure_brain_dir creates the directory."""
        brain_dir = temp_dir / ".claude"
        assert not brain_dir.exists()

        ensure_brain_dir()

        assert brain_dir.exists()
        assert brain_dir.is_dir()

    def test_idempotent(self, temp_dir: Path) -> None:
        """Test that ensure_brain_dir is idempotent."""
        ensure_brain_dir()
        ensure_brain_dir()  # Should not raise

        brain_dir = temp_dir / ".claude"
        assert brain_dir.exists()


class TestCreateGitignore:
    """Tests for create_gitignore function."""

    def test_creates_gitignore(self, temp_dir: Path, mock_brain_dir: Path) -> None:
        """Test that create_gitignore creates the file."""
        result = create_gitignore()

        assert result is True
        gitignore_path = mock_brain_dir / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "code.mv2" in content
        assert "memory.mv2" in content

    def test_does_not_overwrite_existing(
        self, temp_dir: Path, mock_brain_dir: Path
    ) -> None:
        """Test that create_gitignore doesn't overwrite existing file."""
        gitignore_path = mock_brain_dir / ".gitignore"
        gitignore_path.write_text("# Custom gitignore\n")

        result = create_gitignore()

        assert result is False
        content = gitignore_path.read_text()
        assert content == "# Custom gitignore\n"
