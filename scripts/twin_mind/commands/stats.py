"""Stats command for twin-mind."""

from twin_mind.fs import get_code_path, get_memory_path, get_decisions_path
from twin_mind.index_state import load_index_state
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import format_size
from twin_mind.shared_memory import read_shared_memories


def cmd_stats(args):
    """Show twin-mind statistics."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    code_path = get_code_path()
    memory_path = get_memory_path()

    print(f"\nTwin-Mind Stats")
    print("=" * 45)

    # Code stats
    if code_path.exists():
        code_size = format_size(code_path.stat().st_size)
        with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
            stats = mem.stats()
            frame_count = stats.get('frame_count', 0)

        # Get actual file count from index state
        index_state = load_index_state()
        file_count = index_state.get('file_count', '?') if index_state else '?'

        print(f"Code Store:   {code_path}")
        print(f"   Size:         {code_size}")
        print(f"   Files:        {file_count}")
        print(f"   Frames:       {frame_count}")
    else:
        print(f"Code Store:   Not created")

    print()

    # Local memory stats
    if memory_path.exists():
        mem_size = format_size(memory_path.stat().st_size)
        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            stats = mem.stats()
            mem_count = stats.get('frame_count', 0)
        print(f"Local Memory: {memory_path}")
        print(f"   Size:         {mem_size}")
        print(f"   Memories:     {mem_count}")
    else:
        print(f"Local Memory: Not created")

    print()

    # Shared memory stats
    decisions_path = get_decisions_path()
    if decisions_path.exists():
        shared_size = format_size(decisions_path.stat().st_size)
        shared_count = len(read_shared_memories())
        print(f"Shared:       {decisions_path}")
        print(f"   Size:         {shared_size}")
        print(f"   Decisions:    {shared_count}")
    else:
        print(f"Shared:       No shared decisions yet")

    print("=" * 45)
