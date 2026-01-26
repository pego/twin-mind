"""Index state tracking for twin-mind."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from twin_mind.constants import BRAIN_DIR, INDEX_STATE_FILE
from twin_mind.git import get_commits_behind, is_git_repo
from twin_mind.output import warning


def get_index_state_path() -> Path:
    """Get the index state file path."""
    return Path.cwd() / BRAIN_DIR / INDEX_STATE_FILE


def load_index_state() -> Optional[Dict[str, Any]]:
    """Load index state from file."""
    state_path = get_index_state_path()
    if not state_path.exists():
        return None
    try:
        with open(state_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_index_state(commit: str, file_count: int) -> None:
    """Save index state to file."""
    state = {
        "last_commit": commit,
        "indexed_at": datetime.now().isoformat(),
        "file_count": file_count,
    }
    state_path = get_index_state_path()
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def get_index_age() -> Optional[str]:
    """Get human-readable index age."""
    state = load_index_state()
    if not state or "indexed_at" not in state:
        return None

    try:
        indexed_at = datetime.fromisoformat(state["indexed_at"])
        delta = datetime.now() - indexed_at

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"
    except (ValueError, KeyError):
        return None


def check_stale_index(quiet: bool = False) -> bool:
    """Check if index is stale and optionally print warning.

    Returns True if index is stale (or missing).
    """
    if not is_git_repo():
        return False  # Can't determine staleness without git

    state = load_index_state()
    if not state or "last_commit" not in state:
        if not quiet:
            print(warning("No index state found. Run: twin-mind index"))
        return True

    last_commit = state["last_commit"]
    commits_behind = get_commits_behind(last_commit)

    if commits_behind > 0:
        if not quiet:
            print(warning(f"Index may be stale ({commits_behind} commits behind)"))
            print("   Run: twin-mind index")
        return True

    return False
