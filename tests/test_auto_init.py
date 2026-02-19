"""Tests for twin_mind.auto_init module."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestShouldAutoInit:
    """Tests for should_auto_init decision logic."""

    @patch("twin_mind.auto_init.has_code_files")
    @patch("twin_mind.auto_init.is_safe_directory")
    @patch("twin_mind.auto_init.get_brain_dir")
    def test_should_auto_init_true_for_search(
        self,
        mock_get_brain_dir: MagicMock,
        mock_is_safe_directory: MagicMock,
        mock_has_code_files: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Auto-init should run for commands that require stores when environment is safe."""
        mock_get_brain_dir.return_value = temp_dir / ".claude-missing"
        mock_is_safe_directory.return_value = True
        mock_has_code_files.return_value = True

        from twin_mind.auto_init import should_auto_init

        assert should_auto_init("search") is True

    def test_should_auto_init_false_for_init_command(self) -> None:
        """Init command never triggers auto-init."""
        from twin_mind.auto_init import should_auto_init

        assert should_auto_init("init") is False


class TestAutoInitExecution:
    """Tests for auto_init execution path."""

    @patch("twin_mind.auto_init.save_index_state")
    @patch("twin_mind.auto_init.get_current_commit")
    @patch("twin_mind.auto_init.is_git_repo")
    @patch("twin_mind.auto_init.detect_language", return_value="python")
    @patch("twin_mind.auto_init.collect_files")
    @patch("twin_mind.auto_init.get_config")
    @patch("twin_mind.auto_init.get_memory_path")
    @patch("twin_mind.auto_init.get_code_path")
    @patch("twin_mind.auto_init.create_gitignore")
    @patch("twin_mind.auto_init.ensure_brain_dir")
    @patch("twin_mind.auto_init.get_memvid_sdk")
    def test_auto_init_success(
        self,
        mock_get_memvid_sdk: MagicMock,
        mock_ensure_brain_dir: MagicMock,
        mock_create_gitignore: MagicMock,
        mock_get_code_path: MagicMock,
        mock_get_memory_path: MagicMock,
        mock_get_config: MagicMock,
        mock_collect_files: MagicMock,
        mock_detect_language: MagicMock,
        mock_is_git_repo: MagicMock,
        mock_get_current_commit: MagicMock,
        mock_save_index_state: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Auto-init creates stores, indexes files, and records state in git repos."""
        code_path = temp_dir / ".claude" / "code.mv2"
        memory_path = temp_dir / ".claude" / "memory.mv2"
        source_file = temp_dir / "app.py"
        source_file.write_text("print('hello')\n")

        mock_get_code_path.return_value = code_path
        mock_get_memory_path.return_value = memory_path
        mock_get_config.return_value = {}
        mock_collect_files.return_value = [source_file]
        mock_is_git_repo.return_value = True
        mock_get_current_commit.return_value = "abc123"

        mock_mem = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_memvid_sdk.return_value = mock_sdk

        from twin_mind.auto_init import auto_init

        result = auto_init(Namespace())

        assert result is True
        assert mock_mem.put.call_count >= 2  # init memory + at least one indexed file
        mock_save_index_state.assert_called_once_with("abc123", 1)

    @patch("twin_mind.auto_init.get_memvid_sdk")
    def test_auto_init_returns_false_on_failure(
        self, mock_get_memvid_sdk: MagicMock, temp_dir: Path
    ) -> None:
        """Auto-init returns False when store creation raises an exception."""
        mock_sdk = MagicMock()
        mock_sdk.use.side_effect = RuntimeError("store busy")
        mock_get_memvid_sdk.return_value = mock_sdk

        from twin_mind.auto_init import auto_init

        assert auto_init(Namespace()) is False
