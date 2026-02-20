"""Index command for twin-mind."""

import sys
from pathlib import Path
from typing import Any

from twin_mind.config import get_config
from twin_mind.fs import FileLock, get_brain_dir, get_code_path, get_decisions_path
from twin_mind.git import get_changed_files, get_commits_behind, get_current_commit, is_git_repo
from twin_mind.index_state import load_index_state, save_index_state
from twin_mind.indexing import (
    collect_files,
    index_files_full,
    index_files_incremental,
    remove_indexed_paths,
)
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import (
    Colors,
    error,
    format_size,
    info,
    success,
    supports_color,
    warn_if_large,
    warning,
)
from twin_mind.shared_memory import build_decisions_index

try:
    from twin_mind.entity_graph import rebuild_entity_graph, update_entity_graph_incremental
except ImportError:
    rebuild_entity_graph = None  # type: ignore[assignment]
    update_entity_graph_incremental = None  # type: ignore[assignment]


def cmd_index(args: Any) -> None:
    """Index codebase into code store."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    verbose = config.get("output", {}).get("verbose", False) or getattr(args, "verbose", False)
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
                stale_targets = list(dict.fromkeys(changed_files + deleted_files))
                removed = remove_indexed_paths(mem, stale_targets, verbose=verbose)
                if removed > 0:
                    print(info(f"Removed {removed} stale entries"))
                indexed = index_files_incremental(mem, changed_files, config, args)
            else:
                removed = 0
                indexed = index_files_full(mem, config, args)

            try:
                stats = mem.stats()
                total_indexed = int(stats.get("frame_count", indexed))
            except Exception:
                total_indexed = indexed

    # Save state
    current_commit = get_current_commit()
    if current_commit:
        save_index_state(current_commit, total_indexed)

    print(f"\n{success('Done!')} Indexed {indexed} files")
    if incremental and removed:
        print(f"   Removed stale entries: {removed}")
    print(f"   Total indexed files: {total_indexed}")
    print(f"   Size: {format_size(code_path.stat().st_size)}")

    if config.get("maintenance", {}).get("size_warnings", True):
        warn_if_large(code_path, config.get("maintenance", {}).get("code_max_mb", 50), "Code index")

    # Build/update entities graph from Python files
    entities_cfg = config.get("entities", {})
    if entities_cfg.get("enabled", False) and rebuild_entity_graph and update_entity_graph_incremental:
        try:
            if incremental:
                entity_files, entity_count, relation_count = update_entity_graph_incremental(
                    changed_files,
                    deleted_files,
                    config,
                )
            else:
                files = collect_files(config)
                entity_files, entity_count, relation_count = rebuild_entity_graph(
                    files, codebase_root=Path.cwd()
                )
            print(
                f"   Entities: {entity_files} files |"
                f" {entity_count} entities | {relation_count} relations"
            )
        except Exception as e:
            print(warning(f"Entity extraction skipped: {e}"))
    elif entities_cfg.get("enabled", False):
        print(warning("Entity extraction unavailable in this installation (partial upgrade)."))

    # Rebuild decisions semantic index on full reindex (not incremental)
    if not incremental and config.get("decisions", {}).get("build_semantic_index", True):
        decisions_path = get_decisions_path()
        if decisions_path.exists():
            build_decisions_index()
