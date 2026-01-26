"""Tests for the stats command."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdStats:
    """Tests for cmd_stats function."""

    def test_stats_not_initialized(self, tmp_path: Any, capsys: Any) -> None:
        """Test stats when not initialized."""
        with (
            patch("twin_mind.commands.stats.check_memvid"),
            patch("twin_mind.commands.stats.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.stats.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.stats.get_decisions_path", return_value=tmp_path / "none.jsonl"),
            patch("twin_mind.commands.stats.load_index_state", return_value=None),
            patch("twin_mind.commands.stats.read_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.stats import cmd_stats

            args = MockArgs()
            cmd_stats(args)

        captured = capsys.readouterr()
        assert "Stats" in captured.out or "No" in captured.out or "code" in captured.out.lower()

    def test_stats_with_code_index(self, tmp_path: Any, capsys: Any) -> None:
        """Test stats with code index."""
        code_path = tmp_path / "code.mv2"
        code_path.write_bytes(b"x" * 1024)

        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.stats.return_value = {
            "total_entries": 10,
            "total_tokens": 5000,
        }
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.commands.stats.get_code_path", return_value=code_path),
            patch("twin_mind.commands.stats.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.stats.get_decisions_path", return_value=tmp_path / "none.jsonl"),
            patch("twin_mind.commands.stats.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.stats.check_memvid"),
            patch("twin_mind.commands.stats.load_index_state", return_value={"indexed_files": ["a.py", "b.py"]}),
            patch("twin_mind.commands.stats.read_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.stats import cmd_stats

            args = MockArgs()
            cmd_stats(args)

        captured = capsys.readouterr()
        assert "Stats" in captured.out or "code" in captured.out.lower() or "10" in captured.out

    def test_stats_with_memory(self, tmp_path: Any, capsys: Any) -> None:
        """Test stats with memory store."""
        memory_path = tmp_path / "memory.mv2"
        memory_path.write_bytes(b"x" * 512)

        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.stats.return_value = {
            "total_entries": 5,
            "total_tokens": 2000,
        }
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.commands.stats.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.stats.get_memory_path", return_value=memory_path),
            patch("twin_mind.commands.stats.get_decisions_path", return_value=tmp_path / "none.jsonl"),
            patch("twin_mind.commands.stats.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.stats.check_memvid"),
            patch("twin_mind.commands.stats.load_index_state", return_value=None),
            patch("twin_mind.commands.stats.read_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.stats import cmd_stats

            args = MockArgs()
            cmd_stats(args)

        captured = capsys.readouterr()
        assert "Stats" in captured.out or "memory" in captured.out.lower() or "5" in captured.out
