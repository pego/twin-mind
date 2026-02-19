"""Tests for twin_mind.commands.recent module."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCmdRecent:
    """Tests for cmd_recent command."""

    @patch("twin_mind.commands.recent.read_shared_memories", return_value=[])
    @patch("twin_mind.commands.recent.get_memory_path")
    def test_recent_no_memories(
        self,
        mock_get_memory_path: MagicMock,
        mock_read_shared: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Prints a friendly message when no local/shared memories exist."""
        mock_get_memory_path.return_value = temp_dir / ".claude" / "none.mv2"

        from twin_mind.commands.recent import cmd_recent

        cmd_recent(Namespace(n=10))

        captured = capsys.readouterr()
        assert "No memories yet" in captured.out

    @patch("twin_mind.commands.recent.check_memvid")
    @patch("twin_mind.commands.recent.get_memvid_sdk")
    @patch("twin_mind.commands.recent.read_shared_memories")
    @patch("twin_mind.commands.recent.get_memory_path")
    def test_recent_merges_local_and_shared(
        self,
        mock_get_memory_path: MagicMock,
        mock_read_shared: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Includes and sorts local + shared memories in output."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        memory_path = brain_dir / "memory.mv2"
        memory_path.write_text("")
        mock_get_memory_path.return_value = memory_path

        mock_mem = MagicMock()
        mock_mem.timeline.return_value = [
            {
                "preview": "Local note\ntitle: Local Title\nuri: twin-mind://memory/1\ntags: a",
                "timestamp": 100,
            }
        ]
        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sdk.return_value = mock_sdk

        mock_read_shared.return_value = [
            {
                "ts": "2026-02-19T14:00:00",
                "msg": "Shared decision",
                "tag": "arch",
                "author": "alice",
            }
        ]

        from twin_mind.commands.recent import cmd_recent

        cmd_recent(Namespace(n=10))

        captured = capsys.readouterr()
        assert "[shared]" in captured.out
        assert "[local]" in captured.out
        assert "Shared decision" in captured.out
        assert "Local Title" in captured.out
