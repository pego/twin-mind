"""Tests for the prune command."""

from typing import Any
from unittest.mock import MagicMock, patch


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCmdPrune:
    """Tests for cmd_prune function."""

    def test_prune_tag_matches_structured_tags(self, tmp_path: Any, capsys: Any) -> None:
        """Tag pruning should match structured `category:<tag>` metadata."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        memory_path = brain_dir / "memory.mv2"
        memory_path.touch()

        mock_mem = MagicMock()
        mock_mem.timeline.return_value = [
            {
                "uri": "twin-mind://memory/20240101_000000",
                "preview": (
                    "Decision note\n"
                    "title: API auth decision\n"
                    "uri: twin-mind://memory/20240101_000000\n"
                    "tags: category:arch,timestamp:2024-01-01T00:00:00"
                ),
            }
        ]
        mock_sdk = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.commands.prune.check_memvid"),
            patch("twin_mind.commands.prune.get_memvid_sdk", return_value=mock_sdk),
            patch("twin_mind.commands.prune.get_memory_path", return_value=memory_path),
            patch("twin_mind.commands.prune.get_config", return_value={"output": {"color": False}}),
            patch("twin_mind.commands.prune.supports_color", return_value=False),
        ):
            from twin_mind.commands.prune import cmd_prune

            args = MockArgs(before=None, tag="arch", dry_run=True, force=False)
            cmd_prune(args)

        captured = capsys.readouterr()
        assert "Matching: 1 memories" in captured.out
        assert "Would keep 0 memories" in captured.out
