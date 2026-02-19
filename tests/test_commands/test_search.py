"""Tests for the search command."""

import json
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdSearch:
    """Tests for cmd_search function."""

    @pytest.fixture
    def mock_memvid(self) -> MagicMock:
        """Create a mock memvid SDK."""
        mock = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {
            "hits": [
                {
                    "title": "test.py",
                    "text": "def test_function(): pass",
                    "score": 0.95,
                    "uri": "twin-mind://code/test.py",
                }
            ]
        }
        mock.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock.use.return_value.__exit__ = MagicMock(return_value=False)
        return mock

    def test_search_code_only(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test searching code only."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(query="test", scope="code", top_k=5, json=False, context=None, full=False, no_adaptive=False)
            cmd_search(args)

        captured = capsys.readouterr()
        assert "test.py" in captured.out
        assert "Score:" in captured.out

    def test_search_json_output(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test JSON output format."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(query="test", scope="code", top_k=5, json=True, context=None, full=False, no_adaptive=False)
            cmd_search(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["query"] == "test"
        assert "results" in output
        assert len(output["results"]) == 1
        assert output["results"][0]["source"] == "code"

    def test_search_json_extracts_file_path_from_file_uri(
        self, tmp_path: Any, capsys: Any
    ) -> None:
        """JSON output should include file_path for file:// URIs."""
        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {
            "hits": [
                {
                    "title": "src/auth/login.py",
                    "text": "def login(): pass",
                    "score": 0.91,
                    "uri": "file://src/auth/login.py",
                }
            ]
        }
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(
                query="login",
                scope="code",
                top_k=5,
                json=True,
                context=None,
                full=False,
                no_adaptive=False,
            )
            cmd_search(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["results"][0]["file_path"] == "src/auth/login.py"

    def test_search_no_results(self, tmp_path: Any, capsys: Any) -> None:
        """Test search with no results."""
        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {"hits": []}
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(query="nonexistent", scope="all", top_k=5, json=False, context=None, full=False, no_adaptive=False)
            cmd_search(args)

        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_search_memory_scope(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Test searching memory scope."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        memory_path = brain_dir / "memory.mv2"
        memory_path.touch()

        mock_memvid.use.return_value.__enter__.return_value.find.return_value = {
            "hits": [
                {
                    "title": "Remember this",
                    "text": "Important decision about auth",
                    "score": 0.85,
                    "uri": "twin-mind://memory/20240101",
                }
            ]
        }

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memory_path", return_value=memory_path),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(query="auth", scope="memory", top_k=5, json=False, context=None, full=False, no_adaptive=False)
            cmd_search(args)

        captured = capsys.readouterr()
        assert "Remember this" in captured.out or "memory" in captured.out.lower()

    def test_search_scope_filters_results(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Results outside dir_scope are excluded."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        # URI is outside src/auth/ scope
        mock_memvid.use.return_value.__enter__.return_value.find.return_value = {
            "hits": [
                {
                    "title": "other/module.py",
                    "text": "def auth(): pass",
                    "score": 0.9,
                    "uri": "other/module.py",
                }
            ]
        }

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(
                query="auth", scope="code", top_k=5, json=False,
                context=None, full=False, no_adaptive=False, dir_scope="src/auth/",
            )
            cmd_search(args)

        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_search_scope_allows_matching_results(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """Results inside dir_scope pass through."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        mock_memvid.use.return_value.__enter__.return_value.find.return_value = {
            "hits": [
                {
                    "title": "src/auth/login.py",
                    "text": "def login(): pass",
                    "score": 0.9,
                    "uri": "src/auth/login.py",
                }
            ]
        }

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(
                query="auth", scope="code", top_k=5, json=False,
                context=None, full=False, no_adaptive=False, dir_scope="src/auth/",
            )
            cmd_search(args)

        captured = capsys.readouterr()
        assert "src/auth/login.py" in captured.out
        assert "[scope: src/auth/]" in captured.out

    def test_search_no_dir_scope_passes_all(
        self, tmp_path: Any, mock_memvid: MagicMock, capsys: Any
    ) -> None:
        """When dir_scope is None, no filtering is applied."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        code_path = brain_dir / "code.mv2"
        code_path.touch()

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=code_path),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.check_stale_index"),
            patch("twin_mind.commands.search.search_shared_memories", return_value=[]),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(
                query="test", scope="code", top_k=5, json=False,
                context=None, full=False, no_adaptive=False, dir_scope=None,
            )
            cmd_search(args)

        captured = capsys.readouterr()
        assert "test.py" in captured.out
        assert "[scope:" not in captured.out

    def test_search_includes_shared_memories(
        self, tmp_path: Any, capsys: Any
    ) -> None:
        """Test that search includes shared memories."""
        mock_memvid = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {"hits": []}
        mock_memvid.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_memvid.use.return_value.__exit__ = MagicMock(return_value=False)

        shared_results = [
            (8.5, {"msg": "Use JWT for auth", "tag": "arch", "ts": "2024-01-01T10:00:00", "author": "dev"})
        ]

        with (
            patch("twin_mind.commands.search.get_code_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memory_path", return_value=tmp_path / "none.mv2"),
            patch("twin_mind.commands.search.get_memvid_sdk", return_value=mock_memvid),
            patch("twin_mind.commands.search.check_memvid"),
            patch("twin_mind.commands.search.get_config", return_value={
                "output": {"color": False},
                "index": {"adaptive_retrieval": False},
            }),
            patch("twin_mind.commands.search.search_shared_memories", return_value=shared_results),
        ):
            from twin_mind.commands.search import cmd_search

            args = MockArgs(query="auth", scope="memory", top_k=5, json=False, context=None, full=False, no_adaptive=False)
            cmd_search(args)

        captured = capsys.readouterr()
        assert "shared" in captured.out.lower() or "JWT" in captured.out
