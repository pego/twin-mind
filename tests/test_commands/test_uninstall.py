"""Tests for the uninstall command."""

from typing import Any
from unittest.mock import patch


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdUninstall:
    """Tests for cmd_uninstall function."""

    def test_uninstall_lists_canonical_skill_dir(self, tmp_path: Any, capsys: Any) -> None:
        """Uninstall output should include ~/.agents canonical skill path."""
        install_dir = tmp_path / ".twin-mind"
        install_dir.mkdir(parents=True)
        canonical_skill_dir = tmp_path / ".agents" / "skills" / "twin-mind"
        canonical_skill_dir.mkdir(parents=True)

        with (
            patch("twin_mind.commands.uninstall.Path.home", return_value=tmp_path),
            patch("twin_mind.commands.uninstall.confirm", return_value=False),
        ):
            from twin_mind.commands.uninstall import cmd_uninstall

            args = MockArgs(force=False)
            cmd_uninstall(args)

        captured = capsys.readouterr()
        assert str(canonical_skill_dir) in captured.out
