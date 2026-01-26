"""Tests for twin_mind.git module."""

import os
import subprocess
from pathlib import Path
from typing import Generator

import pytest

from twin_mind.git import (
    get_branch_name,
    get_changed_files,
    get_commits_behind,
    get_current_commit,
    get_git_author,
    is_git_repo,
)


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_returns_true_in_git_repo(self, git_repo: Path) -> None:
        """Test that is_git_repo returns True in a git repository."""
        assert is_git_repo() is True

    def test_returns_false_outside_git_repo(self, temp_dir: Path) -> None:
        """Test that is_git_repo returns False outside a git repository."""
        assert is_git_repo() is False


class TestGetCurrentCommit:
    """Tests for get_current_commit function."""

    def test_returns_commit_sha(self, git_repo: Path) -> None:
        """Test that get_current_commit returns a valid SHA."""
        commit = get_current_commit()
        assert commit is not None
        assert len(commit) == 40  # Git SHA is 40 hex characters
        assert all(c in "0123456789abcdef" for c in commit)

    def test_returns_none_outside_git_repo(self, temp_dir: Path) -> None:
        """Test that get_current_commit returns None outside a git repo."""
        commit = get_current_commit()
        assert commit is None


class TestGetChangedFiles:
    """Tests for get_changed_files function."""

    def test_detects_changed_files(self, git_repo: Path) -> None:
        """Test that get_changed_files detects modified files."""
        # Get the initial commit
        initial_commit = get_current_commit()
        assert initial_commit is not None

        # Create a new file and commit it
        new_file = git_repo / "new_file.py"
        new_file.write_text("# New file\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add new file"],
            cwd=git_repo,
            capture_output=True,
        )

        changed, deleted = get_changed_files(initial_commit)
        assert "new_file.py" in changed
        assert deleted == []

    def test_detects_deleted_files(self, git_repo: Path) -> None:
        """Test that get_changed_files detects deleted files."""
        # Get the initial commit
        initial_commit = get_current_commit()
        assert initial_commit is not None

        # Delete README.md and commit
        readme = git_repo / "README.md"
        readme.unlink()
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Delete README"],
            cwd=git_repo,
            capture_output=True,
        )

        changed, deleted = get_changed_files(initial_commit)
        assert "README.md" in deleted

    def test_returns_empty_for_same_commit(self, git_repo: Path) -> None:
        """Test that get_changed_files returns empty lists for same commit."""
        commit = get_current_commit()
        assert commit is not None

        changed, deleted = get_changed_files(commit)
        assert changed == []
        assert deleted == []


class TestGetCommitsBehind:
    """Tests for get_commits_behind function."""

    def test_returns_zero_for_same_commit(self, git_repo: Path) -> None:
        """Test that get_commits_behind returns 0 for same commit."""
        commit = get_current_commit()
        assert commit is not None

        behind = get_commits_behind(commit)
        assert behind == 0

    def test_returns_commit_count(self, git_repo: Path) -> None:
        """Test that get_commits_behind returns correct count."""
        initial_commit = get_current_commit()
        assert initial_commit is not None

        # Make two more commits
        for i in range(2):
            new_file = git_repo / f"file{i}.txt"
            new_file.write_text(f"File {i}\n")
            subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=git_repo,
                capture_output=True,
            )

        behind = get_commits_behind(initial_commit)
        assert behind == 2

    def test_returns_negative_for_invalid_commit(self, git_repo: Path) -> None:
        """Test that get_commits_behind returns -1 for invalid commit."""
        behind = get_commits_behind("invalid_commit_sha")
        assert behind == -1


class TestGetBranchName:
    """Tests for get_branch_name function."""

    def test_returns_branch_name(self, git_repo: Path) -> None:
        """Test that get_branch_name returns the current branch."""
        branch = get_branch_name()
        # Default branch could be 'main' or 'master' depending on git config
        assert branch in ["main", "master"]

    def test_returns_unknown_outside_repo(self, temp_dir: Path) -> None:
        """Test that get_branch_name returns 'unknown' outside a repo."""
        branch = get_branch_name()
        assert branch == "unknown"


class TestGetGitAuthor:
    """Tests for get_git_author function."""

    def test_returns_configured_author(self, git_repo: Path) -> None:
        """Test that get_git_author returns the configured author."""
        author = get_git_author()
        assert author == "Test User"

    def test_returns_fallback_outside_repo(self, temp_dir: Path) -> None:
        """Test that get_git_author returns a fallback outside a repo."""
        author = get_git_author()
        # Should return USER or USERNAME env var, or 'unknown'
        assert author is not None
        assert len(author) > 0
