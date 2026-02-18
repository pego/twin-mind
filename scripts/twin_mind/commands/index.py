"""Index command for twin-mind."""

import sys
from typing import Any

from twin_mind.config import get_config
from twin_mind.fs import FileLock, get_brain_dir, get_code_path, get_decisions_path
from twin_mind.shared_memory import build_decisions_index
from twin_mind.git import get_changed_files, get_commits_behind, get_current_commit, is_git_repo
from twin_mind.index_state import load_index_state, save_index_state
from twin_mind.indexing import collect_files, index_files_full, index_files_incremental
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import Colors, error, format_size, info, success, supports_color, warn_if_large


def cmd_index(args: Any) -> None:
    """Index codebase into code store."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    code_path = get_code_path()

    # Initialize colors based on config
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    if not get_brain_dir().exists():
        print(error("Twin-Mind not initialized. Run: twin-mind init"))
        sys.exit(1)

    # Determine indexing mode
    incremental = False
    changed_files = []
    deleted_files = []
    state = load_index_state()

    if args.fresh:
        # Fresh index requested
        if code_path.exists():
            print(info("Fresh index requested, resetting code store..."))
            code_path.unlink()
    elif state and is_git_repo():
        # Try incremental
        last_commit = state.get("last_commit")
        if last_commit:
            commits_behind = get_commits_behind(last_commit)
            if commits_behind == 0:
                print(success("Index is up to date (no new commits)"))
                return
            elif commits_behind > 0:
                changed_files, deleted_files = get_changed_files(last_commit)
                if changed_files or deleted_files:
                    incremental = True
                    print(info(f"Incremental index (since {last_commit[:7]})"))
                    print(f"   Changed: {len(changed_files)} files")
                    print(f"   Deleted: {len(deleted_files)} files")
                else:
                    print(success("Index is up to date"))
                    return

    # Dry run mode
    if getattr(args, "dry_run", False) or getattr(args, "status", False):
        if incremental:
            print("\n   Would reindex:")
            for f in changed_files[:10]:
                print(f"   + {f}")
            if len(changed_files) > 10:
                print(f"   ... and {len(changed_files) - 10} more")
        else:
            files = collect_files(config)
            print(f"\n   Would index {len(files)} files")
            for f in files[:10]:
                print(f"   + {f.relative_to(get_brain_dir().parent)}")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more")
        return

    # Use file locking for writes
    with FileLock(code_path):
        # Determine mode
        mode = "open" if code_path.exists() else "create"

        if code_path.exists() and not incremental:
            print(info("Appending to existing code index..."))
            print("   (Use --fresh for clean reindex)")

        with memvid_sdk.use("basic", str(code_path), mode=mode) as mem:
            if incremental:
                indexed = index_files_incremental(mem, changed_files, config, args)
            else:
                indexed = index_files_full(mem, config, args)

    # Save state
    current_commit = get_current_commit()
    if current_commit:
        save_index_state(current_commit, indexed)

    print(f"\n{success('Done!')} Indexed {indexed} files")
    print(f"   Size: {format_size(code_path.stat().st_size)}")

    if config.get("maintenance", {}).get("size_warnings", True):
        warn_if_large(code_path, config.get("maintenance", {}).get("code_max_mb", 50), "Code index")

    # Rebuild decisions semantic index on full reindex (not incremental)
    if not incremental and config.get("decisions", {}).get("build_semantic_index", True):
        decisions_path = get_decisions_path()
        if decisions_path.exists():
            build_decisions_index()
