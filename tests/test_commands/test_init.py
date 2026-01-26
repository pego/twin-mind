"""Tests for twin_mind.commands.init module."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCmdInit:
    """Tests for cmd_init command."""

    @pytest.fixture
    def mock_memvid_sdk(self) -> MagicMock:
        """Create a mock memvid_sdk."""
        mock_sdk = MagicMock()
        mock_context = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        return mock_sdk

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    def test_init_creates_directories(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that init creates the .claude directory."""
        from twin_mind.commands.init import cmd_init

        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(banner=False)
        cmd_init(args)

        brain_dir = temp_dir / ".claude"
        assert brain_dir.exists()

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    def test_init_creates_gitignore(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that init creates .gitignore file."""
        from twin_mind.commands.init import cmd_init

        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(banner=False)
        cmd_init(args)

        gitignore = temp_dir / ".claude" / ".gitignore"
        assert gitignore.exists()

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    def test_init_creates_stores(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that init creates code and memory stores."""
        from twin_mind.commands.init import cmd_init

        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(banner=False)
        cmd_init(args)

        # Verify memvid.use was called for both stores
        calls = mock_memvid_sdk.use.call_args_list
        paths = [str(call[0][1]) for call in calls]
        assert any("code.mv2" in p for p in paths)
        assert any("memory.mv2" in p for p in paths)

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    @patch("twin_mind.commands.init.confirm")
    def test_init_prompts_on_existing(
        self,
        mock_confirm: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
    ) -> None:
        """Test that init prompts when stores already exist."""
        from twin_mind.commands.init import cmd_init

        mock_get_sdk.return_value = mock_memvid_sdk
        mock_confirm.return_value = False

        # Create existing stores
        (mock_brain_dir / "code.mv2").write_text("")
        (mock_brain_dir / "memory.mv2").write_text("")

        args = Namespace(banner=False)
        cmd_init(args)

        mock_confirm.assert_called_once()

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    @patch("twin_mind.commands.init.print_banner")
    def test_init_prints_banner(
        self,
        mock_banner: MagicMock,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that init prints banner when requested."""
        from twin_mind.commands.init import cmd_init

        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(banner=True)
        cmd_init(args)

        mock_banner.assert_called_once()

    @patch("twin_mind.commands.init.check_memvid")
    @patch("twin_mind.commands.init.get_memvid_sdk")
    def test_init_adds_welcome_memory(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that init adds a welcome memory to memory store."""
        from twin_mind.commands.init import cmd_init

        mock_mem = MagicMock()
        mock_memvid_sdk.use.return_value.__enter__.return_value = mock_mem
        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(banner=False)
        cmd_init(args)

        # Check that put was called with init message
        put_calls = mock_mem.put.call_args_list
        assert len(put_calls) > 0
        # The last put call should be for the welcome message
        call_kwargs = put_calls[-1][1]
        assert "Twin-Mind" in call_kwargs.get("title", "")
