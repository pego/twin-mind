"""Tests for twin_mind.commands.export module."""

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCmdExport:
    """Tests for cmd_export command."""

    @patch("twin_mind.commands.export.check_memvid")
    @patch("twin_mind.commands.export.get_memory_path")
    def test_export_exits_when_store_missing(
        self,
        mock_get_memory_path: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Export exits when memory store is not initialized."""
        mock_get_memory_path.return_value = temp_dir / ".claude" / "none.mv2"

        from twin_mind.commands.export import cmd_export

        with pytest.raises(SystemExit):
            cmd_export(Namespace(format="md", output=None))

    @patch("twin_mind.commands.export.check_memvid")
    @patch("twin_mind.commands.export.get_memvid_sdk")
    @patch("twin_mind.commands.export.get_memory_path")
    def test_export_json_to_file(
        self,
        mock_get_memory_path: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """JSON export writes parsed memories to output file."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        memory_path = brain_dir / "memory.mv2"
        memory_path.write_text("")
        mock_get_memory_path.return_value = memory_path

        mock_mem = MagicMock()
        mock_mem.timeline.return_value = [
            {
                "preview": "Decision text\ntitle: Decision 1\nuri: twin-mind://memory/abc\ntags: category:arch",
                "uri": "twin-mind://memory/abc",
            }
        ]
        mock_mem.frame.return_value = {
            "title": "Decision 1",
            "tags": ["category:arch"],
            "uri": "twin-mind://memory/abc",
        }

        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sdk.return_value = mock_sdk

        out_path = temp_dir / "memory.json"

        from twin_mind.commands.export import cmd_export

        cmd_export(Namespace(format="json", output=str(out_path)))

        captured = capsys.readouterr()
        assert "Exported 1 memories" in captured.out
        data = json.loads(out_path.read_text())
        assert data[0]["title"] == "Decision 1"
        assert data[0]["content"] == "Decision text"

    @patch("twin_mind.commands.export.check_memvid")
    @patch("twin_mind.commands.export.get_memvid_sdk")
    @patch("twin_mind.commands.export.get_memory_path")
    def test_export_markdown_stdout(
        self,
        mock_get_memory_path: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Markdown export prints a readable report when no output file is provided."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        memory_path = brain_dir / "memory.mv2"
        memory_path.write_text("")
        mock_get_memory_path.return_value = memory_path

        mock_mem = MagicMock()
        mock_mem.timeline.return_value = [
            {
                "preview": "Memory body\ntitle: Memory 1\nuri: twin-mind://memory/xyz\ntags: category:todo",
                "uri": "twin-mind://memory/xyz",
            }
        ]
        mock_mem.frame.return_value = {
            "title": "Memory 1",
            "tags": ["category:todo"],
            "uri": "twin-mind://memory/xyz",
        }

        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sdk.return_value = mock_sdk

        from twin_mind.commands.export import cmd_export

        cmd_export(Namespace(format="md", output=None))

        captured = capsys.readouterr()
        assert "# Twin-Mind Memory Export" in captured.out
        assert "Memory 1" in captured.out
