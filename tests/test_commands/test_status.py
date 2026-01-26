"""Tests for the status command."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdStatus:
    """Tests for cmd_status function."""

    def test_status_not_initialized(self, tmp_path: Any, capsys: Any) -> None:
        """Test status when not initialized."""
        with (
            patch("twin_mind.commands.status.check_memvid"),
            patch("twin_mind.commands.status.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.status.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.status.get_decisions_path", return_value=tmp_path / "none.jsonl"),
            patch("twin_mind.commands.status.get_config", return_value={"output": {"color": False}}),
            patch("twin_mind.commands.status.supports_color", return_value=False),
            patch("twin_mind.commands.status.load_index_state", return_value=None),
            patch("twin_mind.commands.status.is_git_repo", return_value=False),
        ):
            from twin_mind.commands.status import cmd_status

            args = MockArgs(json=False)
            cmd_status(args)

        captured = capsys.readouterr()
        assert "Status" in captured.out or "code" in captured.out.lower()

    def test_status_initialized(self, tmp_path: Any, capsys: Any) -> None:
        """Test status when initialized."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.write_bytes(b"x" * 1024)
        memory_path = brain_dir / "memory.mv2"
        memory_path.write_bytes(b"x" * 512)

        index_state = {
            "last_commit": "abc123",
            "indexed_files": ["file1.py", "file2.py"],
            "timestamp": "2024-01-01T10:00:00",
        }

        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.stats.return_value = {"total_entries": 10}
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.commands.status.get_code_path", return_value=code_path),
            patch("twin_mind.commands.status.get_memory_path", return_value=memory_path),
            patch("twin_mind.commands.status.get_decisions_path", return_value=tmp_path / "none.jsonl"),
            patch("twin_mind.commands.status.get_config", return_value={"output": {"color": False}}),
            patch("twin_mind.commands.status.supports_color", return_value=False),
            patch("twin_mind.commands.status.load_index_state", return_value=index_state),
            patch("twin_mind.commands.status.get_index_age", return_value="1 hour ago"),
            patch("twin_mind.commands.status.is_git_repo", return_value=True),
            patch("twin_mind.commands.status.get_current_commit", return_value="abc123"),
            patch("twin_mind.commands.status.get_commits_behind", return_value=0),
            patch("twin_mind.commands.status.get_branch_name", return_value="main"),
            patch("twin_mind.commands.status.check_memvid"),
            patch("twin_mind.commands.status.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.status.read_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.status import cmd_status

            args = MockArgs(json=False)
            cmd_status(args)

        captured = capsys.readouterr()
        assert "Status" in captured.out or "code" in captured.out.lower()
