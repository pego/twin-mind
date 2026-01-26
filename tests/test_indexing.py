"""Tests for twin_mind.indexing module."""

from pathlib import Path
from typing import Any, Dict

import pytest

from twin_mind.indexing import (
    collect_files,
    detect_language,
    get_memvid_create_kwargs,
)


class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_python(self) -> None:
        """Test detecting Python files."""
        assert detect_language(".py") == "python"
        assert detect_language(".PY") == "python"  # Case insensitive

    def test_javascript(self) -> None:
        """Test detecting JavaScript files."""
        assert detect_language(".js") == "javascript"
        assert detect_language(".jsx") == "javascript"

    def test_typescript(self) -> None:
        """Test detecting TypeScript files."""
        assert detect_language(".ts") == "typescript"
        assert detect_language(".tsx") == "typescript"

    def test_java(self) -> None:
        """Test detecting Java files."""
        assert detect_language(".java") == "java"

    def test_go(self) -> None:
        """Test detecting Go files."""
        assert detect_language(".go") == "go"

    def test_rust(self) -> None:
        """Test detecting Rust files."""
        assert detect_language(".rs") == "rust"

    def test_c_cpp(self) -> None:
        """Test detecting C/C++ files."""
        assert detect_language(".c") == "c"
        assert detect_language(".cpp") == "cpp"

    def test_ruby(self) -> None:
        """Test detecting Ruby files."""
        assert detect_language(".rb") == "ruby"

    def test_php(self) -> None:
        """Test detecting PHP files."""
        assert detect_language(".php") == "php"

    def test_sql(self) -> None:
        """Test detecting SQL files."""
        assert detect_language(".sql") == "sql"

    def test_shell(self) -> None:
        """Test detecting shell scripts."""
        assert detect_language(".sh") == "bash"

    def test_markdown(self) -> None:
        """Test detecting Markdown files."""
        assert detect_language(".md") == "markdown"

    def test_yaml(self) -> None:
        """Test detecting YAML files."""
        assert detect_language(".yaml") == "yaml"

    def test_json(self) -> None:
        """Test detecting JSON files."""
        assert detect_language(".json") == "json"

    def test_html_css(self) -> None:
        """Test detecting HTML/CSS files."""
        assert detect_language(".html") == "html"
        assert detect_language(".css") == "css"

    def test_vue_svelte(self) -> None:
        """Test detecting Vue/Svelte files."""
        assert detect_language(".vue") == "vue"
        assert detect_language(".svelte") == "svelte"

    def test_graphql(self) -> None:
        """Test detecting GraphQL files."""
        assert detect_language(".graphql") == "graphql"

    def test_protobuf(self) -> None:
        """Test detecting Protocol Buffer files."""
        assert detect_language(".proto") == "protobuf"

    def test_unknown_extension(self) -> None:
        """Test unknown extensions default to 'text'."""
        assert detect_language(".xyz") == "text"
        assert detect_language(".unknown") == "text"
        assert detect_language("") == "text"


class TestCollectFiles:
    """Tests for collect_files function."""

    def test_collects_python_files(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test collecting Python files."""
        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "utils.py" in file_names

    def test_collects_javascript_files(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test collecting JavaScript files."""
        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "app.js" in file_names

    def test_collects_json_files(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test collecting JSON files."""
        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "config.json" in file_names

    def test_skips_excluded_directories(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test that excluded directories are skipped."""
        # Create a node_modules directory with a file
        node_modules = sample_project / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.js").write_text("// package\n")

        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "package.js" not in file_names

    def test_skips_hidden_directories(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test that hidden directories are skipped."""
        # Create a hidden directory with a file
        hidden = sample_project / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("# secret\n")

        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "secret.py" not in file_names

    def test_respects_max_file_size(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test that files exceeding max size are skipped."""
        # Set a very small max file size
        sample_config["max_file_size"] = "10B"

        files = collect_files(sample_config)

        # All our sample files should be larger than 10 bytes
        assert len(files) == 0

    def test_excludes_extensions(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test excluding specific extensions."""
        sample_config["extensions"]["exclude"] = [".json"]

        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "config.json" not in file_names
        assert "main.py" in file_names

    def test_includes_custom_extensions(
        self, sample_project: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test including custom extensions."""
        # Create a file with custom extension
        (sample_project / "data.custom").write_text("custom data\n")
        sample_config["extensions"]["include"] = [".custom"]

        files = collect_files(sample_config)
        file_names = [f.name for f in files]

        assert "data.custom" in file_names

    def test_empty_directory(self, temp_dir: Path, sample_config: Dict[str, Any]) -> None:
        """Test collecting files from empty directory."""
        files = collect_files(sample_config)
        assert files == []


class TestGetMemvidCreateKwargs:
    """Tests for get_memvid_create_kwargs function."""

    def test_returns_empty_dict_by_default(
        self, sample_config: Dict[str, Any]
    ) -> None:
        """Test that empty dict is returned when no model specified."""
        kwargs = get_memvid_create_kwargs(sample_config)
        assert kwargs == {}

    def test_includes_embedding_model(self, sample_config: Dict[str, Any]) -> None:
        """Test that embedding model is included when specified."""
        sample_config["index"]["embedding_model"] = "bge-small"

        kwargs = get_memvid_create_kwargs(sample_config)

        assert kwargs == {"model": "bge-small"}

    def test_handles_none_model(self, sample_config: Dict[str, Any]) -> None:
        """Test handling of explicit None model."""
        sample_config["index"]["embedding_model"] = None

        kwargs = get_memvid_create_kwargs(sample_config)

        assert kwargs == {}
