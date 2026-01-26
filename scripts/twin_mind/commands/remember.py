"""Remember command for twin-mind."""

import sys
from datetime import datetime

from twin_mind.config import get_config
from twin_mind.fs import get_memory_path
from twin_mind.git import get_git_author
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.shared_memory import write_shared_memory


def cmd_remember(args):
    """Store a memory/decision/insight."""
    config = get_config()

    # Determine destination: shared (decisions.jsonl) or local (memory.mv2)
    # Priority: explicit flags > config > default (local)
    use_shared = False
    if hasattr(args, 'share') and args.share:
        use_shared = True
    elif hasattr(args, 'local') and args.local:
        use_shared = False
    elif config["memory"].get("share_memories", False):
        use_shared = True

    # Create title from message
    title = args.message[:50]
    if len(args.message) > 50:
        title += "..."

    tag_str = f" [{args.tag}]" if args.tag else ""

    if use_shared:
        # Write to shared decisions.jsonl
        if write_shared_memory(args.message, args.tag):
            author = get_git_author()
            print(f"Shared{tag_str}: {title}")
            print(f"   Added to decisions.jsonl (by {author})")
        else:
            sys.exit(1)
    else:
        # Write to local memory.mv2
        check_memvid()
        memvid_sdk = get_memvid_sdk()
        memory_path = get_memory_path()

        if not memory_path.exists():
            print("Twin-Mind not initialized. Run: twin-mind init")
            sys.exit(1)

        # Build tags for memvid
        tags = [f"timestamp:{datetime.now().isoformat()}"]
        if args.tag:
            tags.append(f"category:{args.tag}")
        else:
            tags.append("category:general")

        # Check deduplication setting
        use_dedupe = config["memory"].get("dedupe", True)

        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            try:
                # Try with dedupe parameter if supported
                mem.put(
                    title=title,
                    text=args.message,
                    uri=f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    tags=tags,
                    dedupe=use_dedupe
                )
            except TypeError:
                # Fallback if memvid doesn't support dedupe parameter
                mem.put(
                    title=title,
                    text=args.message,
                    uri=f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    tags=tags
                )

        dedupe_note = " (dedupe)" if use_dedupe else ""
        print(f"Remembered{tag_str}: {title}")
        print(f"   Saved to local memory.mv2{dedupe_note}")
