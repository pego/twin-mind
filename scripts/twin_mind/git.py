"""Git integration for twin-mind."""

import os
import subprocess
from pathlib import Path


def is_git_repo() -> bool:
    """Check if current directory is a git repo."""
    try:
        subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True, check=True, cwd=Path.cwd()
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_current_commit() -> str | None:
    """Get current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_changed_files(since_commit: str) -> tuple[list[str], list[str]]:
    """Get changed and deleted files since a commit.

    Returns: (changed_files, deleted_files)
    """
    changed = []
    deleted = []

    try:
        # Changed/added files
        result = subprocess.run(
            ['git', 'diff', '--name-only', since_commit, 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        changed = [f for f in result.stdout.strip().split('\n') if f]

        # Deleted files
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=D', since_commit, 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        deleted = [f for f in result.stdout.strip().split('\n') if f]

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return changed, deleted


def get_commits_behind(since_commit: str) -> int:
    """Get number of commits between since_commit and HEAD."""
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'{since_commit}..HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return -1


def get_branch_name() -> str:
    """Get current branch name."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def get_git_author() -> str:
    """Get author name from git config or environment."""
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    # Fallback to environment or username
    return os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
