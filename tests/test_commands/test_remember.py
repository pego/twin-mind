"""Tests for twin_mind.commands.remember module."""

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCmdRemember:
    """Tests for cmd_remember command."""

    @pytest.fixture
    def mock_memvid_sdk(self) -> MagicMock:
        """Create a mock memvid_sdk."""
        mock_sdk = MagicMock()
        mock_context = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)
        return mock_sdk

    @patch("twin_mind.commands.remember.check_memvid")
    @patch("twin_mind.commands.remember.get_memvid_sdk")
    def test_remember_saves_to_local(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
    ) -> None:
        """Test remembering to local memory store."""
        from twin_mind.commands.remember import cmd_remember

        mock_mem = MagicMock()
        mock_memvid_sdk.use.return_value.__enter__.return_value = mock_mem
        mock_get_sdk.return_value = mock_memvid_sdk

        # Create memory store file
        (mock_brain_dir / "memory.mv2").write_text("")

        args = Namespace(
            message="Test memory message",
            tag="test",
            local=False,
            share=False,
        )
        cmd_remember(args)

        # Verify put was called
        mock_mem.put.assert_called_once()
        call_kwargs = mock_mem.put.call_args[1]
        assert "Test memory" in call_kwargs["text"]
        assert any("category:test" in t for t in call_kwargs["tags"])

    @patch("twin_mind.commands.remember.write_shared_memory")
    def test_remember_saves_to_shared(
        self,
        mock_write_shared: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
    ) -> None:
        """Test remembering to shared decisions file."""
        from twin_mind.commands.remember import cmd_remember

        mock_write_shared.return_value = True

        args = Namespace(
            message="Shared decision",
            tag="arch",
            local=False,
            share=True,  # Force shared
        )
        cmd_remember(args)

        mock_write_shared.assert_called_once_with("Shared decision", "arch")

    @patch("twin_mind.commands.remember.check_memvid")
    @patch("twin_mind.commands.remember.get_memvid_sdk")
    def test_remember_truncates_long_title(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
    ) -> None:
        """Test that long messages are truncated for title."""
        from twin_mind.commands.remember import cmd_remember

        mock_mem = MagicMock()
        mock_memvid_sdk.use.return_value.__enter__.return_value = mock_mem
        mock_get_sdk.return_value = mock_memvid_sdk

        # Create memory store file
        (mock_brain_dir / "memory.mv2").write_text("")

        long_message = "A" * 100  # 100 character message

        args = Namespace(
            message=long_message,
            tag=None,
            local=False,
            share=False,
        )
        cmd_remember(args)

        call_kwargs = mock_mem.put.call_args[1]
        title = call_kwargs["title"]
        # Title should be truncated to 50 chars + "..."
        assert len(title) == 53
        assert title.endswith("...")

    @patch("twin_mind.commands.remember.check_memvid")
    @patch("twin_mind.commands.remember.get_memvid_sdk")
    def test_remember_adds_default_tag(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
    ) -> None:
        """Test that default 'general' tag is added when no tag specified."""
        from twin_mind.commands.remember import cmd_remember

        mock_mem = MagicMock()
        mock_memvid_sdk.use.return_value.__enter__.return_value = mock_mem
        mock_get_sdk.return_value = mock_memvid_sdk

        # Create memory store file
        (mock_brain_dir / "memory.mv2").write_text("")

        args = Namespace(
            message="Test message",
            tag=None,  # No tag specified
            local=False,
            share=False,
        )
        cmd_remember(args)

        call_kwargs = mock_mem.put.call_args[1]
        tags = call_kwargs["tags"]
        assert any("category:general" in t for t in tags)

    @patch("twin_mind.commands.remember.check_memvid")
    @patch("twin_mind.commands.remember.get_memvid_sdk")
    def test_remember_exits_if_not_initialized(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that remember exits if twin-mind not initialized."""
        from twin_mind.commands.remember import cmd_remember

        mock_get_sdk.return_value = mock_memvid_sdk

        args = Namespace(
            message="Test message",
            tag=None,
            local=False,
            share=False,
        )

        with pytest.raises(SystemExit):
            cmd_remember(args)

    @patch("twin_mind.commands.remember.write_shared_memory")
    @patch("twin_mind.commands.remember.get_config")
    def test_remember_respects_config_share_memories(
        self,
        mock_get_config: MagicMock,
        mock_write_shared: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
        sample_config: dict,
    ) -> None:
        """Test that remember respects share_memories config."""
        from twin_mind.commands.remember import cmd_remember

        sample_config["memory"]["share_memories"] = True
        mock_get_config.return_value = sample_config
        mock_write_shared.return_value = True

        args = Namespace(
            message="Config-shared memory",
            tag="test",
            local=False,
            share=False,  # Not explicitly shared, but config says to share
        )
        cmd_remember(args)

        mock_write_shared.assert_called_once()

    @patch("twin_mind.commands.remember.write_shared_memory")
    @patch("twin_mind.commands.remember.get_config")
    @patch("twin_mind.commands.remember.check_memvid")
    @patch("twin_mind.commands.remember.get_memvid_sdk")
    def test_remember_local_flag_overrides_config(
        self,
        mock_get_sdk: MagicMock,
        mock_check: MagicMock,
        mock_get_config: MagicMock,
        mock_write_shared: MagicMock,
        mock_memvid_sdk: MagicMock,
        temp_dir: Path,
        mock_brain_dir: Path,
        sample_config: dict,
    ) -> None:
        """Test that --local flag overrides share_memories config."""
        from twin_mind.commands.remember import cmd_remember

        sample_config["memory"]["share_memories"] = True
        mock_get_config.return_value = sample_config

        mock_mem = MagicMock()
        mock_memvid_sdk.use.return_value.__enter__.return_value = mock_mem
        mock_get_sdk.return_value = mock_memvid_sdk

        # Create memory store file
        (mock_brain_dir / "memory.mv2").write_text("")

        args = Namespace(
            message="Local override memory",
            tag="test",
            local=True,  # Explicitly local
            share=False,
        )
        cmd_remember(args)

        # Should NOT call write_shared_memory
        mock_write_shared.assert_not_called()
        # Should call memvid put
        mock_mem.put.assert_called_once()
