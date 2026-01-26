"""Prune command for twin-mind."""

import re
import shutil
import sys
from datetime import datetime, timedelta
from typing import Any

from twin_mind.config import get_config
from twin_mind.fs import get_memory_path
from twin_mind.memory import parse_timeline_entry
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import Colors, confirm, error, success, supports_color


def cmd_prune(args: Any) -> None:
    """Prune old memories via filtered rebuild."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print(error("No memory store. Run: twin-mind init"))
        sys.exit(1)

    # Parse date filter
    cutoff = None
    if args.before:
        if re.match(r"^\d+d$", args.before):
            days = int(args.before[:-1])
            cutoff = datetime.now() - timedelta(days=days)
        elif re.match(r"^\d+w$", args.before):
            weeks = int(args.before[:-1])
            cutoff = datetime.now() - timedelta(weeks=weeks)
        else:
            try:
                cutoff = datetime.fromisoformat(args.before)
            except ValueError:
                print(error(f"Invalid date format: {args.before}"))
                print("   Use: YYYY-MM-DD, 30d (days), or 2w (weeks)")
                sys.exit(1)

    if not cutoff and not args.tag:
        print(error("Specify --before DATE or --tag TAG to prune"))
        sys.exit(1)

    # Load all memories using timeline
    with memvid_sdk.use("basic", str(memory_path), mode="open") as mem:
        all_entries = mem.timeline()

    if not all_entries:
        print("No memories to prune")
        return

    # Filter memories to remove
    to_remove = []
    to_keep = []

    for entry in all_entries:
        should_remove = False
        uri = entry.get("uri", "")
        preview = entry.get("preview", "")

        # Skip system entries - always keep
        if uri and "twin-mind://system" in uri:
            to_keep.append(entry)
            continue

        # Check date filter
        if cutoff and uri:
            try:
                # URI format: twin-mind://memory/YYYYMMDD_HHMMSS
                if "twin-mind://memory/" in uri:
                    date_part = uri.split("/")[-1]
                    mem_date = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                    if mem_date < cutoff:
                        should_remove = True
            except (ValueError, IndexError):
                pass

        # Check tag filter
        if args.tag:
            tag_lower = args.tag.lower()
            # Extract title from preview
            title = ""
            if "\ntitle: " in preview:
                title = preview.split("\ntitle: ")[1].split("\n")[0]
            if tag_lower in title.lower() or f"[{tag_lower}]" in preview.lower():
                should_remove = True

        if should_remove:
            to_remove.append(entry)
        else:
            to_keep.append(entry)

    if not to_remove:
        print(success("No memories match prune criteria"))
        return

    # Show preview
    print("\nPrune preview:")
    print(f"   Matching: {len(to_remove)} memories")
    for entry in to_remove[:5]:
        parsed = parse_timeline_entry(entry)
        title = parsed["title"][:50]
        print(f'   - "{title}"')
    if len(to_remove) > 5:
        print(f"   ... and {len(to_remove) - 5} more")

    # Dry run stops here
    if getattr(args, "dry_run", False):
        print(f"\n   Would keep {len(to_keep)} memories")
        return

    # Confirm
    if not getattr(args, "force", False):
        if not confirm(f"\nDelete {len(to_remove)} memories?"):
            print("   Cancelled")
            return

    # Backup
    from pathlib import Path

    backup_path = Path(str(memory_path) + ".backup")
    shutil.copy2(memory_path, backup_path)
    print(f"Backed up to {backup_path}")

    # Rebuild with kept memories
    memory_path.unlink()
    with memvid_sdk.use("basic", str(memory_path), mode="create") as new_mem:
        for entry in to_keep:
            parsed = parse_timeline_entry(entry)
            new_mem.put(
                title=parsed["title"],
                text=parsed["text"],
                uri=parsed["uri"]
                or f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                tags=parsed["tags"],
            )

    print(success(f"Pruned {len(to_remove)} memories ({len(to_keep)} remaining)"))
