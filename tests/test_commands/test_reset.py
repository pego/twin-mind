"""Tests for twin_mind.commands.reset module."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCmdReset:
    """Tests for cmd_reset command."""

    @patch("twin_mind.commands.reset.check_memvid")
    @patch("twin_mind.commands.reset.get_memvid_sdk")
    @patch("twin_mind.commands.reset.get_code_path")
    @patch("twin_mind.commands.reset.get_memory_path")
    def test_reset_dry_run_preview(
        self,
        mock_get_memory_path: MagicMock,
        mock_get_code_path: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Dry-run mode previews resets without mutating stores."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        memory_path = brain_dir / "memory.mv2"
        code_path.write_bytes(b"x" * 128)
        memory_path.write_bytes(b"x" * 256)

        mock_get_code_path.return_value = code_path
        mock_get_memory_path.return_value = memory_path

        from twin_mind.commands.reset import cmd_reset

        cmd_reset(Namespace(target="all", force=False, dry_run=True))

        captured = capsys.readouterr()
        assert "Would reset code store" in captured.out
        assert "Would reset memory store" in captured.out
        assert code_path.exists()
        assert memory_path.exists()
        mock_get_sdk.return_value.use.assert_not_called()

    @patch("twin_mind.commands.reset.check_memvid")
    @patch("twin_mind.commands.reset.get_memvid_sdk")
    @patch("twin_mind.commands.reset.get_code_path")
    @patch("twin_mind.commands.reset.get_memory_path")
    def test_reset_memory_force_recreates_store(
        self,
        mock_get_memory_path: MagicMock,
        mock_get_code_path: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Force reset recreates memory store and writes reset entry."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        memory_path = brain_dir / "memory.mv2"
        code_path.write_text("")
        memory_path.write_text("seed")

        mock_get_code_path.return_value = code_path
        mock_get_memory_path.return_value = memory_path

        mock_mem = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sdk.return_value = mock_sdk

        from twin_mind.commands.reset import cmd_reset

        cmd_reset(Namespace(target="memory", force=True, dry_run=False))

        captured = capsys.readouterr()
        assert "Memory store reset" in captured.out
        mock_mem.put.assert_called_once()
