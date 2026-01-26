"""Status command for twin-mind."""

from twin_mind.config import get_config
from twin_mind.fs import get_code_path, get_memory_path, get_decisions_path
from twin_mind.git import is_git_repo, get_branch_name, get_current_commit, get_commits_behind
from twin_mind.index_state import load_index_state, get_index_age
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import Colors, supports_color, success, warning, format_size
from twin_mind.shared_memory import read_shared_memories


def cmd_status(args):
    """Show twin-mind health status."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    code_path = get_code_path()
    memory_path = get_memory_path()

    print(f"\nTwin-Mind Status")
    print("=" * 50)

    # Code stats
    if code_path.exists():
        code_size = format_size(code_path.stat().st_size)
        try:
            with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
                stats = mem.stats()
                frame_count = stats.get('frame_count', 0)
        except Exception:
            frame_count = "?"

        # Get actual file count from index state
        index_state = load_index_state()
        file_count = index_state.get('file_count', '?') if index_state else '?'

        age = get_index_age() or "unknown"
        print(f"Code     {code_size:>8} | {file_count} files, {frame_count} frames | indexed {age}")
    else:
        print(f"Code     {warning('not created')}")

    # Local memory stats
    if memory_path.exists():
        mem_size = format_size(memory_path.stat().st_size)
        try:
            with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
                stats = mem.stats()
                mem_count = stats.get('frame_count', 0)
        except Exception:
            mem_count = "?"
        print(f"Local    {mem_size:>8} | {mem_count} entries")
    else:
        print(f"Local    {warning('not created')}")

    # Shared memory stats
    decisions_path = get_decisions_path()
    if decisions_path.exists():
        shared_size = format_size(decisions_path.stat().st_size)
        shared_count = len(read_shared_memories())
        print(f"Shared   {shared_size:>8} | {shared_count} decisions")
    else:
        print(f"Shared   {'none':>8} | (use --share or set share_memories: true)")

    # Git status
    if is_git_repo():
        branch = get_branch_name()
        commit = get_current_commit()
        commit_short = commit[:7] if commit else "?"

        state = load_index_state()
        if state and commit:
            behind = get_commits_behind(state.get("last_commit", commit))
            if behind > 0:
                git_status = warning(f"{behind} commits ahead of index")
            elif behind == 0:
                git_status = success("up to date")
            else:
                git_status = "unknown"
        else:
            git_status = "not indexed yet"

        print(f"Git      {branch} @ {commit_short} ({git_status})")

    print("=" * 50)
