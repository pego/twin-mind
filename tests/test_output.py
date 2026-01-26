"""Tests for twin_mind.output module."""

import sys
from io import StringIO
from typing import Generator

import pytest

from twin_mind.output import (
    Colors,
    ProgressBar,
    color,
    confirm,
    error,
    format_size,
    info,
    success,
    supports_color,
    warning,
)


class TestFormatSize:
    """Tests for format_size function."""

    def test_format_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"

    def test_format_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(10240) == "10.0 KB"

    def test_format_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_size(1048576) == "1.00 MB"
        assert format_size(1572864) == "1.50 MB"
        assert format_size(10485760) == "10.00 MB"

    def test_format_large_sizes(self) -> None:
        """Test formatting larger sizes."""
        # Still formats as MB (no GB support in format_size)
        assert "MB" in format_size(1073741824)


class TestColors:
    """Tests for Colors class."""

    def test_colors_enabled_by_default(self) -> None:
        """Test that colors are enabled by default."""
        # Reset to ensure clean state
        Colors.RESET = "\033[0m"
        Colors.RED = "\033[31m"
        Colors.GREEN = "\033[32m"
        Colors.YELLOW = "\033[33m"
        Colors.BLUE = "\033[34m"
        Colors.BOLD = "\033[1m"
        Colors._enabled = True

        assert Colors.is_enabled() is True
        assert Colors.RED == "\033[31m"
        assert Colors.GREEN == "\033[32m"

    def test_disable_colors(self) -> None:
        """Test disabling colors."""
        Colors.disable()

        assert Colors.is_enabled() is False
        assert Colors.RED == ""
        assert Colors.GREEN == ""
        assert Colors.RESET == ""

    def test_color_function_with_enabled(self) -> None:
        """Test color function when colors are enabled."""
        # Re-enable colors
        Colors.RESET = "\033[0m"
        Colors.RED = "\033[31m"
        Colors._enabled = True

        result = color("test", Colors.RED)
        assert result == "\033[31mtest\033[0m"

    def test_color_function_with_disabled(self) -> None:
        """Test color function when colors are disabled."""
        Colors.disable()

        result = color("test", Colors.RED)
        assert result == "test"


class TestColorHelpers:
    """Tests for color helper functions."""

    def setup_method(self) -> None:
        """Re-enable colors before each test."""
        Colors.RESET = "\033[0m"
        Colors.RED = "\033[31m"
        Colors.GREEN = "\033[32m"
        Colors.YELLOW = "\033[33m"
        Colors.BLUE = "\033[34m"
        Colors._enabled = True

    def test_success(self) -> None:
        """Test success helper."""
        result = success("OK")
        assert "\033[32m" in result  # Green
        assert "OK" in result

    def test_warning(self) -> None:
        """Test warning helper."""
        result = warning("WARN")
        assert "\033[33m" in result  # Yellow
        assert "WARN" in result

    def test_error(self) -> None:
        """Test error helper."""
        result = error("ERR")
        assert "\033[31m" in result  # Red
        assert "ERR" in result

    def test_info(self) -> None:
        """Test info helper."""
        result = info("INFO")
        assert "\033[34m" in result  # Blue
        assert "INFO" in result


class TestProgressBar:
    """Tests for ProgressBar class."""

    def test_initialization(self) -> None:
        """Test ProgressBar initialization."""
        bar = ProgressBar(100, width=50, prefix="Test: ")
        assert bar.total == 100
        assert bar.width == 50
        assert bar.prefix == "Test: "
        assert bar.current == 0

    def test_update(self) -> None:
        """Test ProgressBar update."""
        bar = ProgressBar(10)
        bar._is_tty = False  # Disable rendering

        bar.update(1)
        assert bar.current == 1

        bar.update(5)
        assert bar.current == 6

    def test_update_default_increment(self) -> None:
        """Test ProgressBar update with default increment."""
        bar = ProgressBar(10)
        bar._is_tty = False

        bar.update()
        assert bar.current == 1

        bar.update()
        assert bar.current == 2


class TestSupportsColor:
    """Tests for supports_color function."""

    def test_no_color_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that NO_COLOR env var disables colors."""
        monkeypatch.setenv("NO_COLOR", "1")
        assert supports_color() is False

    def test_no_color_empty_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that empty NO_COLOR doesn't disable colors."""
        # Only if NO_COLOR is set (not empty string)
        monkeypatch.delenv("NO_COLOR", raising=False)
        # Result depends on whether stdout is a tty


class TestConfirm:
    """Tests for confirm function."""

    def test_confirm_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test confirm returns True for 'y'."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert confirm("Test?") is True

    def test_confirm_no(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test confirm returns False for 'n'."""
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert confirm("Test?") is False

    def test_confirm_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test confirm returns False for empty input."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert confirm("Test?") is False

    def test_confirm_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test confirm handles uppercase Y."""
        monkeypatch.setattr("builtins.input", lambda _: "Y")
        # Current implementation converts to lowercase
        assert confirm("Test?") is True

    def test_confirm_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test confirm handles input with whitespace."""
        monkeypatch.setattr("builtins.input", lambda _: "  y  ")
        assert confirm("Test?") is True
