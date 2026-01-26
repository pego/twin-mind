"""Tests for the index command."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdIndex:
    """Tests for cmd_index function."""

    def test_index_not_initialized(self, tmp_path: Any, capsys: Any) -> None:
        """Test index when not initialized."""
        with (
            patch("twin_mind.commands.index.check_memvid"),
            patch("twin_mind.commands.index.get_brain_dir", return_value=tmp_path / ".claude"),
            patch("twin_mind.commands.index.get_config", return_value={"output": {"color": False}}),
            patch("twin_mind.commands.index.supports_color", return_value=False),
        ):
            from twin_mind.commands.index import cmd_index

            args = MockArgs(fresh=False, status=False)

            with pytest.raises(SystemExit):
                cmd_index(args)

        captured = capsys.readouterr()
        assert "not initialized" in captured.out.lower() or "init" in captured.out.lower()


class TestCollectFiles:
    """Tests for file collection logic."""

    def test_collect_files_basic(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that collect_files finds Python files."""
        # Create test files
        (tmp_path / "test.py").write_text("python")
        (tmp_path / "test.js").write_text("javascript")
        (tmp_path / "test.txt").write_text("text")

        # Change to tmp_path since collect_files uses Path.cwd()
        monkeypatch.chdir(tmp_path)

        from twin_mind.indexing import collect_files
        from twin_mind.constants import CODE_EXTENSIONS, SKIP_DIRS, MAX_FILE_SIZE

        config = {"max_file_size": "500KB"}

        with (
            patch("twin_mind.indexing.get_extensions", return_value=CODE_EXTENSIONS),
            patch("twin_mind.indexing.get_skip_dirs", return_value=SKIP_DIRS),
            patch("twin_mind.indexing.parse_size", return_value=MAX_FILE_SIZE),
        ):
            files = collect_files(config)

        filenames = [f.name for f in files]
        assert "test.py" in filenames
        assert "test.js" in filenames

    def test_collect_files_skips_hidden(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that collect_files skips hidden directories."""
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.py").write_text("secret")
        (tmp_path / "visible.py").write_text("visible")

        # Change to tmp_path since collect_files uses Path.cwd()
        monkeypatch.chdir(tmp_path)

        from twin_mind.indexing import collect_files
        from twin_mind.constants import CODE_EXTENSIONS, SKIP_DIRS, MAX_FILE_SIZE

        config = {"max_file_size": "500KB"}

        with (
            patch("twin_mind.indexing.get_extensions", return_value=CODE_EXTENSIONS),
            patch("twin_mind.indexing.get_skip_dirs", return_value=SKIP_DIRS),
            patch("twin_mind.indexing.parse_size", return_value=MAX_FILE_SIZE),
        ):
            files = collect_files(config)

        filenames = [f.name for f in files]
        assert "visible.py" in filenames
        assert "secret.py" not in filenames

    def test_collect_files_skips_node_modules(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that collect_files skips node_modules."""
        node_dir = tmp_path / "node_modules"
        node_dir.mkdir()
        (node_dir / "package.js").write_text("package")
        (tmp_path / "app.js").write_text("app")

        # Change to tmp_path since collect_files uses Path.cwd()
        monkeypatch.chdir(tmp_path)

        from twin_mind.indexing import collect_files
        from twin_mind.constants import CODE_EXTENSIONS, SKIP_DIRS, MAX_FILE_SIZE

        config = {"max_file_size": "500KB"}

        with (
            patch("twin_mind.indexing.get_extensions", return_value=CODE_EXTENSIONS),
            patch("twin_mind.indexing.get_skip_dirs", return_value=SKIP_DIRS),
            patch("twin_mind.indexing.parse_size", return_value=MAX_FILE_SIZE),
        ):
            files = collect_files(config)

        filenames = [f.name for f in files]
        assert "app.js" in filenames
        assert "package.js" not in filenames
