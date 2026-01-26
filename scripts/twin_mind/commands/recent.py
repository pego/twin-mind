"""Recent command for twin-mind."""

from datetime import datetime
from typing import Any

from twin_mind.fs import get_memory_path
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.shared_memory import read_shared_memories


def cmd_recent(args: Any) -> None:
    """Show recent memories (local + shared)."""
    all_entries = []

    # Get local memories from memory.mv2
    memory_path = get_memory_path()
    if memory_path.exists():
        check_memvid()
        memvid_sdk = get_memvid_sdk()
        with memvid_sdk.use("basic", str(memory_path), mode="open") as mem:
            entries = mem.timeline()
            for entry in entries:
                preview = entry.get("preview", "")
                title = "untitled"
                text = preview
                if "\ntitle: " in preview:
                    parts = preview.split("\ntitle: ")
                    text = parts[0]
                    title_part = parts[1].split("\n")[0] if len(parts) > 1 else ""
                    title = title_part or "untitled"
                all_entries.append(
                    {
                        "source": "local",
                        "title": title,
                        "text": text,
                        "timestamp": entry.get("timestamp", 0),
                    }
                )

    # Get shared memories from decisions.jsonl
    shared_memories = read_shared_memories()
    for entry in shared_memories:
        try:
            ts = datetime.fromisoformat(entry.get("ts", "")).timestamp()
        except (ValueError, TypeError):
            ts = 0
        all_entries.append(
            {
                "source": "shared",
                "title": f"[{entry.get('tag', 'general')}] by {entry.get('author', 'unknown')}",
                "text": entry.get("msg", ""),
                "timestamp": ts,
            }
        )

    # Sort by timestamp descending (most recent first) and limit
    all_entries = sorted(all_entries, key=lambda x: x.get("timestamp", 0), reverse=True)[: args.n]

    if not all_entries:
        print("No memories yet. Use: twin-mind remember <message>")
        return

    print(f"\nRecent Memories ({len(all_entries)})\n")
    print("=" * 60)

    for i, entry in enumerate(all_entries, 1):
        icon = "[shared]" if entry["source"] == "shared" else "[local]"
        print(f"\n{icon} [{i}] {entry['title']}")
        print(f"    {entry['text'][:150]}")
