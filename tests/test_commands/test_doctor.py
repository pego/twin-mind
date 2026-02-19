"""Tests for twin_mind.commands.doctor module."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCmdDoctor:
    """Tests for cmd_doctor command."""

    @patch("twin_mind.commands.doctor.check_memvid")
    @patch("twin_mind.commands.doctor.get_memvid_sdk")
    @patch("twin_mind.commands.doctor.get_brain_dir")
    @patch("twin_mind.commands.doctor.get_config")
    @patch("twin_mind.commands.doctor.supports_color")
    def test_doctor_not_initialized(
        self,
        mock_supports_color: MagicMock,
        mock_get_config: MagicMock,
        mock_get_brain_dir: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Doctor exits early with guidance when Twin-Mind is not initialized."""
        mock_supports_color.return_value = False
        mock_get_config.return_value = {"output": {"color": False}}
        mock_get_brain_dir.return_value = temp_dir / ".claude-missing"

        from twin_mind.commands.doctor import cmd_doctor

        cmd_doctor(Namespace(vacuum=False, rebuild=False))

        captured = capsys.readouterr()
        assert "Twin-Mind not initialized" in captured.out

    @patch("twin_mind.commands.doctor.check_memvid")
    @patch("twin_mind.commands.doctor.get_memvid_sdk")
    @patch("twin_mind.commands.doctor.get_config")
    @patch("twin_mind.commands.doctor.supports_color")
    @patch("twin_mind.commands.doctor.read_shared_memories")
    @patch("twin_mind.commands.doctor.load_index_state")
    @patch("twin_mind.commands.doctor.get_index_age")
    @patch("twin_mind.commands.doctor.is_git_repo")
    @patch("twin_mind.commands.doctor.get_commits_behind")
    @patch("twin_mind.commands.doctor.get_brain_dir")
    @patch("twin_mind.commands.doctor.get_code_path")
    @patch("twin_mind.commands.doctor.get_memory_path")
    @patch("twin_mind.commands.doctor.get_decisions_path")
    def test_doctor_reports_malformed_and_stale_index(
        self,
        mock_get_decisions_path: MagicMock,
        mock_get_memory_path: MagicMock,
        mock_get_code_path: MagicMock,
        mock_get_brain_dir: MagicMock,
        mock_get_commits_behind: MagicMock,
        mock_is_git_repo: MagicMock,
        mock_get_index_age: MagicMock,
        mock_load_index_state: MagicMock,
        mock_read_shared_memories: MagicMock,
        mock_supports_color: MagicMock,
        mock_get_config: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check_memvid: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Doctor highlights malformed shared entries and stale index state."""
        brain_dir = temp_dir / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        memory_path = brain_dir / "memory.mv2"
        decisions_path = brain_dir / "decisions.jsonl"
        code_path.write_bytes(b"x" * 1024)
        memory_path.write_bytes(b"x" * 512)
        decisions_path.write_text(
            '{"ts":"2026-01-01T10:00:00","msg":"ok","tag":"arch","author":"alice"}\n'
            "not-json\n"
        )

        mock_get_brain_dir.return_value = brain_dir
        mock_get_code_path.return_value = code_path
        mock_get_memory_path.return_value = memory_path
        mock_get_decisions_path.return_value = decisions_path

        mock_supports_color.return_value = False
        mock_get_config.return_value = {"output": {"color": False}}
        mock_read_shared_memories.return_value = [
            {"ts": "2026-01-01T10:00:00", "msg": "ok", "tag": "arch", "author": "alice"}
        ]
        mock_load_index_state.return_value = {"last_commit": "abc123"}
        mock_get_index_age.return_value = "1d ago"
        mock_is_git_repo.return_value = True
        mock_get_commits_behind.return_value = 3

        mock_mem = MagicMock()
        mock_mem.stats.return_value = {"frame_count": 10}
        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sdk.return_value = mock_sdk

        from twin_mind.commands.doctor import cmd_doctor

        cmd_doctor(Namespace(vacuum=False, rebuild=False))

        captured = capsys.readouterr()
        assert "malformed entries" in captured.out
        assert "commits behind HEAD" in captured.out
