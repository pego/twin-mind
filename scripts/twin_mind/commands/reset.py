"""Reset command for twin-mind."""

from datetime import datetime
from typing import Any

from twin_mind.fs import get_code_path, get_entities_db_path, get_memory_path
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import confirm, format_size, info, success


def cmd_reset(args: Any) -> None:
    """Reset code, memory, or both stores."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    dry_run = getattr(args, "dry_run", False)
    code_path = get_code_path()
    entities_path = get_entities_db_path()
    memory_path = get_memory_path()

    target = args.target

    if dry_run:
        print(info("Reset preview (dry-run):"))

    if target in ("code", "all"):
        if code_path.exists():
            size = format_size(code_path.stat().st_size)
            if dry_run:
                print(f"   Would reset code store ({size})")
                if entities_path.exists():
                    graph_size = format_size(entities_path.stat().st_size)
                    print(f"   Would reset entity graph ({graph_size})")
            elif args.force or confirm(f"Delete code store ({size})?"):
                code_path.unlink()
                with memvid_sdk.use("basic", str(code_path), mode="create") as mem:
                    pass  # Just create empty store
                print(success("Code store reset"))
                if entities_path.exists():
                    entities_path.unlink()
                    print(success("Entity graph reset"))
            else:
                print("   Skipped code store")
        else:
            print("   Code store doesn't exist")

    if target in ("memory", "all"):
        if memory_path.exists():
            size = format_size(memory_path.stat().st_size)
            if dry_run:
                print(f"   Would reset memory store ({size})")
            elif args.force or confirm(f"Delete memory store ({size})? This is PERMANENT!"):
                memory_path.unlink()
                with memvid_sdk.use("basic", str(memory_path), mode="create") as mem:
                    mem.put(
                        title="Memory Reset",
                        text=f"Memory reset on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        uri="twin-mind://system/reset",
                        tags=["category:system", f"timestamp:{datetime.now().isoformat()}"],
                    )
                print(success("Memory store reset"))
            else:
                print("   Skipped memory store")
        else:
            print("   Memory store doesn't exist")
