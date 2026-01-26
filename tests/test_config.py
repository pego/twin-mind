"""Tests for twin_mind.config module."""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from twin_mind.config import (
    get_extensions,
    get_skip_dirs,
    load_config,
    parse_size,
)
from twin_mind.constants import CODE_EXTENSIONS, DEFAULT_CONFIG, SKIP_DIRS


class TestParseSize:
    """Tests for parse_size function."""

    def test_parse_bytes(self) -> None:
        """Test parsing bytes without suffix."""
        assert parse_size("1024") == 1024
        assert parse_size("0") == 0
        assert parse_size("100") == 100

    def test_parse_kilobytes(self) -> None:
        """Test parsing KB suffix."""
        assert parse_size("1KB") == 1024
        assert parse_size("500KB") == 512000
        assert parse_size("1kb") == 1024  # Case insensitive

    def test_parse_megabytes(self) -> None:
        """Test parsing MB suffix."""
        assert parse_size("1MB") == 1048576
        assert parse_size("10MB") == 10485760
        assert parse_size("1mb") == 1048576  # Case insensitive

    def test_parse_gigabytes(self) -> None:
        """Test parsing GB suffix."""
        assert parse_size("1GB") == 1073741824
        assert parse_size("2GB") == 2147483648

    def test_parse_bytes_suffix(self) -> None:
        """Test parsing B suffix."""
        assert parse_size("100B") == 100
        assert parse_size("1024B") == 1024

    def test_parse_float_values(self) -> None:
        """Test parsing float values."""
        assert parse_size("1.5MB") == int(1.5 * 1024 * 1024)
        assert parse_size("0.5KB") == 512

    def test_parse_with_whitespace(self) -> None:
        """Test parsing with leading/trailing whitespace."""
        assert parse_size("  500KB  ") == 512000
        assert parse_size("\t1MB\n") == 1048576


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_default_config(self, temp_dir: Path) -> None:
        """Test loading default config when no settings file exists."""
        config = load_config()
        assert config == DEFAULT_CONFIG

    def test_load_config_with_custom_extensions(
        self, temp_dir: Path, mock_brain_dir: Path
    ) -> None:
        """Test loading config with custom extensions."""
        settings = {
            "twin-mind": {
                "extensions": {"include": [".custom"], "exclude": [".md"]},
            }
        }
        settings_path = mock_brain_dir / "settings.json"
        settings_path.write_text(json.dumps(settings))

        config = load_config()
        assert ".custom" in config["extensions"]["include"]
        assert ".md" in config["extensions"]["exclude"]

    def test_load_config_with_custom_skip_dirs(
        self, temp_dir: Path, mock_brain_dir: Path
    ) -> None:
        """Test loading config with custom skip directories."""
        settings = {
            "twin-mind": {
                "skip_dirs": ["custom_dir", "another_dir"],
            }
        }
        settings_path = mock_brain_dir / "settings.json"
        settings_path.write_text(json.dumps(settings))

        config = load_config()
        assert "custom_dir" in config["skip_dirs"]
        assert "another_dir" in config["skip_dirs"]

    def test_load_config_with_max_file_size(
        self, temp_dir: Path, mock_brain_dir: Path
    ) -> None:
        """Test loading config with custom max file size."""
        settings = {
            "twin-mind": {
                "max_file_size": "1MB",
            }
        }
        settings_path = mock_brain_dir / "settings.json"
        settings_path.write_text(json.dumps(settings))

        config = load_config()
        assert config["max_file_size"] == "1MB"

    def test_load_config_with_invalid_json(
        self, temp_dir: Path, mock_brain_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test loading config with invalid JSON returns defaults."""
        settings_path = mock_brain_dir / "settings.json"
        settings_path.write_text("{ invalid json }")

        config = load_config()
        assert config == DEFAULT_CONFIG


class TestGetExtensions:
    """Tests for get_extensions function."""

    def test_get_default_extensions(self, sample_config: Dict[str, Any]) -> None:
        """Test getting default extensions."""
        extensions = get_extensions(sample_config)
        assert extensions == CODE_EXTENSIONS

    def test_get_extensions_with_includes(self, sample_config: Dict[str, Any]) -> None:
        """Test getting extensions with custom includes."""
        sample_config["extensions"]["include"] = [".custom", "special"]
        extensions = get_extensions(sample_config)
        assert ".custom" in extensions
        assert ".special" in extensions

    def test_get_extensions_with_excludes(self, sample_config: Dict[str, Any]) -> None:
        """Test getting extensions with excludes."""
        sample_config["extensions"]["exclude"] = [".md", ".txt"]
        extensions = get_extensions(sample_config)
        assert ".md" not in extensions
        assert ".txt" not in extensions

    def test_extensions_adds_dot_prefix(self, sample_config: Dict[str, Any]) -> None:
        """Test that extensions without dot prefix get one added."""
        sample_config["extensions"]["include"] = ["custom"]
        extensions = get_extensions(sample_config)
        assert ".custom" in extensions


class TestGetSkipDirs:
    """Tests for get_skip_dirs function."""

    def test_get_default_skip_dirs(self, sample_config: Dict[str, Any]) -> None:
        """Test getting default skip directories."""
        skip_dirs = get_skip_dirs(sample_config)
        assert skip_dirs == SKIP_DIRS

    def test_get_skip_dirs_with_custom(self, sample_config: Dict[str, Any]) -> None:
        """Test getting skip directories with custom additions."""
        sample_config["skip_dirs"] = ["custom_skip", "another_skip"]
        skip_dirs = get_skip_dirs(sample_config)
        assert "custom_skip" in skip_dirs
        assert "another_skip" in skip_dirs
        # Original dirs should still be present
        assert "node_modules" in skip_dirs
        assert "__pycache__" in skip_dirs
