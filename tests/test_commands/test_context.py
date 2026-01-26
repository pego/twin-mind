"""Tests for the context command."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdContext:
    """Tests for cmd_context function."""

    @pytest.fixture
    def mock_memvid(self) -> MagicMock:
        """Create a mock memvid SDK."""
        mock = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {
            "hits": [
                {
                    "title": "auth.py",
                    "text": "def authenticate(user, password): return True",
                    "score": 0.9,
                },
                {
                    "title": "utils.py",
                    "text": "def hash_password(pwd): return hashlib.sha256(pwd)",
                    "score": 0.8,
                },
            ]
        }
        mock.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock.use.return_value.__exit__ = MagicMock(return_value=False)
        return mock

    def test_context_generates_combined_output(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test that context combines code and memory results."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()
        memory_path = brain_dir / "memory.mv2"
        memory_path.touch()

        with (
            patch("twin_mind.commands.context.get_code_path", return_value=code_path),
            patch("twin_mind.commands.context.get_memory_path", return_value=memory_path),
            patch("twin_mind.commands.context.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.context.check_memvid"),
        ):
            from twin_mind.commands.context import cmd_context

            args = MockArgs(query="authentication", max_tokens=4000, json=False)
            cmd_context(args)

        captured = capsys.readouterr()
        assert "Context for:" in captured.out
        assert "auth" in captured.out.lower()

    def test_context_json_output(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test JSON output format for context."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.context.get_code_path", return_value=code_path),
            patch("twin_mind.commands.context.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.context.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.context.check_memvid"),
        ):
            from twin_mind.commands.context import cmd_context

            args = MockArgs(query="auth", max_tokens=4000, json=True)
            cmd_context(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["query"] == "auth"
        assert "context" in output
        assert "code_results" in output

    def test_context_no_results(self, tmp_path: Any, capsys: Any) -> None:
        """Test context when no results found."""
        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {"hits": []}
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.commands.context.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.context.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.context.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.context.check_memvid"),
        ):
            from twin_mind.commands.context import cmd_context

            args = MockArgs(query="nonexistent", max_tokens=4000, json=False)
            cmd_context(args)

        captured = capsys.readouterr()
        assert "No relevant context" in captured.out

    def test_context_respects_token_limit(
        self, tmp_path: Any, capsys: Any
    ) -> None:
        """Test that context respects max_tokens limit."""
        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        # Return a lot of content
        mock_mem.find.return_value = {
            "hits": [
                {"title": f"file{i}.py", "text": "x" * 1000, "score": 0.9 - i * 0.1}
                for i in range(10)
            ]
        }
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.context.get_code_path", return_value=code_path),
            patch("twin_mind.commands.context.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.context.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.context.check_memvid"),
        ):
            from twin_mind.commands.context import cmd_context

            # Use a small token limit
            args = MockArgs(query="test", max_tokens=500, json=True)
            cmd_context(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # Should be limited (500 tokens * 4 chars = 2000 chars max)
        assert output["total_chars"] <= 2500  # Some buffer for formatting

    def test_context_code_only(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test context with only code results."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.context.get_code_path", return_value=code_path),
            patch("twin_mind.commands.context.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.context.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.context.check_memvid"),
        ):
            from twin_mind.commands.context import cmd_context

            args = MockArgs(query="auth", max_tokens=4000, json=True)
            cmd_context(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["code_results"] > 0
        assert output["memory_results"] == 0
