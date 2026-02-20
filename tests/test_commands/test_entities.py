"""Tests for twin_mind.commands.entities module."""

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCmdEntities:
    """Tests for entities command."""

    @patch("twin_mind.commands.entities.get_entities_db_path")
    def test_entities_requires_graph(
        self, mock_get_entities_db_path: MagicMock, temp_dir: Path, capsys: MagicMock
    ) -> None:
        """Command exits with guidance when graph is missing."""
        mock_get_entities_db_path.return_value = temp_dir / ".claude" / "entities.sqlite"

        from twin_mind.commands.entities import cmd_entities

        with pytest.raises(SystemExit):
            cmd_entities(Namespace(action="find", symbol="auth", kind=None, limit=10, json=False))

        captured = capsys.readouterr()
        assert "Run: twin-mind index" in captured.out

    @patch("twin_mind.commands.entities.find_entities")
    @patch("twin_mind.commands.entities.get_entities_db_path")
    def test_entities_find_json(
        self,
        mock_get_entities_db_path: MagicMock,
        mock_find_entities: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Find action supports JSON output."""
        db_path = temp_dir / ".claude" / "entities.sqlite"
        db_path.parent.mkdir(parents=True)
        db_path.write_text("")
        mock_get_entities_db_path.return_value = db_path
        mock_find_entities.return_value = [
            {
                "file_path": "src/auth.py",
                "name": "authenticate",
                "qualname": "src.auth.authenticate",
                "kind": "function",
                "line": 10,
                "score": 1.0,
            }
        ]

        from twin_mind.commands.entities import cmd_entities

        cmd_entities(Namespace(action="find", symbol="authenticate", kind=None, limit=10, json=True))

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["action"] == "find"
        assert output["count"] == 1
        assert output["results"][0]["qualname"] == "src.auth.authenticate"

    @patch("twin_mind.commands.entities.find_callers")
    @patch("twin_mind.commands.entities.get_entities_db_path")
    def test_entities_callers_output(
        self,
        mock_get_entities_db_path: MagicMock,
        mock_find_callers: MagicMock,
        temp_dir: Path,
        capsys: MagicMock,
    ) -> None:
        """Callers action prints caller -> callee relationships."""
        db_path = temp_dir / ".claude" / "entities.sqlite"
        db_path.parent.mkdir(parents=True)
        db_path.write_text("")
        mock_get_entities_db_path.return_value = db_path
        mock_find_callers.return_value = [
            {
                "file_path": "src/api.py",
                "caller": "src.api.login",
                "callee": "authenticate",
                "line": 22,
                "caller_kind": "function",
            }
        ]

        from twin_mind.commands.entities import cmd_entities

        cmd_entities(Namespace(action="callers", symbol="authenticate", limit=10, json=False))

        captured = capsys.readouterr()
        assert "src.api.login -> authenticate" in captured.out
