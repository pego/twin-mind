"""Doctor command for twin-mind."""

import json
from typing import Any

from twin_mind.config import get_config
from twin_mind.fs import get_brain_dir, get_code_path, get_decisions_path, get_memory_path
from twin_mind.git import get_commits_behind, is_git_repo
from twin_mind.index_state import get_index_age, load_index_state
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import Colors, error, format_size, info, success, supports_color, warning
from twin_mind.shared_memory import read_shared_memories


def cmd_doctor(args: Any) -> None:
    """Run diagnostics and maintenance on twin-mind stores."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    code_path = get_code_path()
    memory_path = get_memory_path()
    decisions_path = get_decisions_path()

    do_vacuum = getattr(args, "vacuum", False)
    do_rebuild = getattr(args, "rebuild", False)

    print("\nTwin-Mind Doctor")
    print("=" * 50)

    issues = []
    recommendations = []

    # Check if initialized
    if not get_brain_dir().exists():
        print(error("Twin-Mind not initialized"))
        print("   Run: twin-mind init")
        return

    # Check code store
    print(f"\nCode Store: {code_path}")
    if code_path.exists():
        code_size = code_path.stat().st_size
        code_size / (1024 * 1024)
        print(f"   Size: {format_size(code_size)}")

        try:
            with memvid_sdk.use("basic", str(code_path), mode="open") as mem:
                stats = mem.stats()
                frame_count = stats.get("frame_count", 0)
                print(f"   Frames: {frame_count}")

                # Check for bloat (size vs frame count ratio)
                if frame_count > 0:
                    bytes_per_frame = code_size / frame_count
                    if bytes_per_frame > 50000:  # > 50KB per frame suggests bloat
                        issues.append("Code index may be bloated")
                        recommendations.append("Run: twin-mind doctor --vacuum")

                # Vacuum if requested
                if do_vacuum:
                    print(f"   {info('Vacuuming...')}")
                    try:
                        mem.vacuum()
                        new_size = code_path.stat().st_size
                        saved = code_size - new_size
                        if saved > 0:
                            print(f"   {success(f'Reclaimed {format_size(saved)}')}")
                        else:
                            print(f"   {success('Already optimized')}")
                    except AttributeError:
                        print(f"   {warning('Vacuum not supported in this memvid version')}")

                # Rebuild if requested
                if do_rebuild:
                    print(f"   {info('Rebuilding index...')}")
                    try:
                        mem.rebuild_index()
                        print(f"   {success('Index rebuilt')}")
                    except AttributeError:
                        print(f"   {warning('Rebuild not supported in this memvid version')}")

        except Exception as e:
            issues.append(f"Code store error: {e}")
            print(f"   {error(f'Error: {e}')}")
    else:
        print(f"   {warning('Not created')}")
        recommendations.append("Run: twin-mind index")

    # Check memory store
    print(f"\nMemory Store: {memory_path}")
    if memory_path.exists():
        mem_size = memory_path.stat().st_size
        mem_size_mb = mem_size / (1024 * 1024)
        print(f"   Size: {format_size(mem_size)}")

        # Size warnings based on memvid recommendations
        if mem_size_mb > 15:
            issues.append(f"Memory store is large ({mem_size_mb:.1f}MB)")
            recommendations.append("Consider: twin-mind prune memory --before 30d")

        try:
            with memvid_sdk.use("basic", str(memory_path), mode="open") as mem:
                stats = mem.stats()
                mem_count = stats.get("frame_count", 0)
                print(f"   Entries: {mem_count}")

                # Vacuum if requested
                if do_vacuum:
                    print(f"   {info('Vacuuming...')}")
                    try:
                        mem.vacuum()
                        new_size = memory_path.stat().st_size
                        saved = mem_size - new_size
                        if saved > 0:
                            print(f"   {success(f'Reclaimed {format_size(saved)}')}")
                        else:
                            print(f"   {success('Already optimized')}")
                    except AttributeError:
                        print(f"   {warning('Vacuum not supported in this memvid version')}")

        except Exception as e:
            issues.append(f"Memory store error: {e}")
            print(f"   {error(f'Error: {e}')}")
    else:
        print(f"   {warning('Not created')}")

    # Check shared decisions
    print(f"\nShared Decisions: {decisions_path}")
    if decisions_path.exists():
        decisions_size = decisions_path.stat().st_size
        print(f"   Size: {format_size(decisions_size)}")
        memories = read_shared_memories()
        print(f"   Entries: {len(memories)}")

        # Check for malformed entries
        malformed = 0
        try:
            with open(decisions_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            json.loads(line)
                        except json.JSONDecodeError:
                            malformed += 1
        except Exception:
            pass

        if malformed > 0:
            issues.append(f"{malformed} malformed entries in decisions.jsonl")
            print(f"   {warning(f'{malformed} malformed entries')}")
    else:
        print("   No shared decisions yet")

    # Check index staleness
    print("\nIndex State:")
    state = load_index_state()
    if state:
        age = get_index_age()
        print(f"   Last indexed: {age or 'unknown'}")

        if is_git_repo():
            last_commit = state.get("last_commit", "")
            if last_commit:
                behind = get_commits_behind(last_commit)
                if behind > 0:
                    issues.append(f"Index is {behind} commits behind")
                    print(f"   {warning(f'{behind} commits behind HEAD')}")
                    recommendations.append("Run: twin-mind index")
                elif behind == 0:
                    print(f"   {success('Up to date with HEAD')}")
    else:
        print(f"   {warning('No index state found')}")
        recommendations.append("Run: twin-mind index")

    # Summary
    print(f"\n{'=' * 50}")
    if issues:
        print(f"\nIssues found ({len(issues)}):")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"\n{success('No issues found')}")

    if recommendations:
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"   - {rec}")

    print()
