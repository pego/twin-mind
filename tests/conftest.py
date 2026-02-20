"""Shared fixtures for twin-mind tests."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture
def git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository."""
    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    # Create an initial commit
    test_file = temp_dir / "README.md"
    test_file.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    yield temp_dir


@pytest.fixture
def sample_project(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a sample project with code files."""
    # Create Python files
    src_dir = temp_dir / "src"
    src_dir.mkdir()

    (src_dir / "main.py").write_text('''"""Main module."""


def hello(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(hello("World"))
''')

    (src_dir / "utils.py").write_text('''"""Utility functions."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
''')

    # Create a JavaScript file
    (temp_dir / "app.js").write_text('''// App module
function greet(name) {
    return `Hello, ${name}!`;
}

module.exports = { greet };
''')

    # Create a config file
    (temp_dir / "config.json").write_text('{"debug": true, "version": "1.0.0"}\n')

    yield temp_dir


@pytest.fixture
def mock_brain_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a mock .claude directory."""
    brain_dir = temp_dir / ".claude"
    brain_dir.mkdir()
    yield brain_dir


@pytest.fixture
def sample_config() -> dict:
    """Return a sample configuration dict."""
    return {
        "extensions": {"include": [], "exclude": []},
        "skip_dirs": [],
        "max_file_size": "500KB",
        "index": {
            "auto_incremental": True,
            "track_deletions": True,
            "parallel": True,
            "parallel_workers": 4,
            "embedding_model": None,
            "adaptive_retrieval": True,
        },
        "entities": {"enabled": True},
        "output": {"color": True, "verbose": False},
        "memory": {"share_memories": False, "dedupe": True},
    }
