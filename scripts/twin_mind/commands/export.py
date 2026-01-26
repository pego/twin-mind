"""Export command for twin-mind."""

import json
import sys
from datetime import datetime
from pathlib import Path

from twin_mind.fs import get_memory_path
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.memory import parse_timeline_entry


def cmd_export(args):
    """Export memories to readable format."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print("No memory store. Run: twin-mind init")
        sys.exit(1)

    # Get all memories using timeline, then fetch full frame data
    memories = []
    with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
        entries = mem.timeline()
        for entry in entries:
            # Parse text from preview (before metadata lines)
            parsed = parse_timeline_entry(entry)

            # Get full metadata from frame() for accurate title/tags
            uri = entry.get('uri', '')
            if uri:
                try:
                    frame = mem.frame(uri)
                    parsed['title'] = frame.get('title', parsed['title'])
                    parsed['tags'] = frame.get('tags', parsed['tags'])
                    parsed['uri'] = frame.get('uri', parsed['uri'])
                except Exception:
                    pass  # Use parsed values if frame lookup fails

            memories.append(parsed)

    if not memories:
        print("No memories to export")
        return

    if args.format == 'json':
        output = []
        for mem_data in memories:
            output.append({
                "title": mem_data['title'],
                "content": mem_data['text'],
                "uri": mem_data['uri'],
                "tags": mem_data['tags']
            })
        result = json.dumps(output, indent=2, ensure_ascii=False)
    else:  # markdown
        lines = ["# Twin-Mind Memory Export", ""]
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total memories: {len(memories)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, mem_data in enumerate(memories, 1):
            title = mem_data['title']
            text = mem_data['text'].strip()
            uri = mem_data['uri']
            tags = mem_data['tags']
            lines.append(f"## {i}. {title}")
            lines.append("")
            lines.append(text)
            lines.append("")
            if tags:
                lines.append(f"*Tags: {', '.join(tags)}*")
            if uri:
                lines.append(f"*URI: {uri}*")
            lines.append("")
            lines.append("---")
            lines.append("")

        result = "\n".join(lines)

    # Output to file or stdout
    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"Exported {len(memories)} memories to {args.output}")
    else:
        print(result)
