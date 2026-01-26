"""Context command for twin-mind."""

import json
from typing import Any

from twin_mind.fs import get_code_path, get_memory_path
from twin_mind.memvid_check import check_memvid, get_memvid_sdk


def cmd_context(args: Any) -> None:
    """Generate combined code+memory context for prompts."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    code_path = get_code_path()
    memory_path = get_memory_path()

    query = args.query
    max_tokens = getattr(args, "max_tokens", 4000)

    # Collect results
    code_results = []
    memory_results = []

    # Search code
    if code_path.exists():
        with memvid_sdk.use("basic", str(code_path), mode="open") as mem:
            response = mem.find(query, k=5, snippet_chars=2000)
            code_results = response.get("hits", [])[:3]  # Top 3 code results

    # Search memory
    if memory_path.exists():
        with memvid_sdk.use("basic", str(memory_path), mode="open") as mem:
            response = mem.find(query, k=5, snippet_chars=1000)
            memory_results = response.get("hits", [])[:3]  # Top 3 memory results

    # Build context document
    context_parts = []
    total_chars = 0
    char_limit = max_tokens * 4  # Rough char-to-token ratio

    # Add relevant code first
    if code_results:
        context_parts.append("## Relevant Code\n")
        for hit in code_results:
            if total_chars >= char_limit:
                break
            file_name = hit.get("title", "file")
            text = hit.get("text", "").strip()[:1500]
            code_block = f"### {file_name}\n```\n{text}\n```\n"
            context_parts.append(code_block)
            total_chars += len(code_block)

    # Add relevant memories
    if memory_results:
        context_parts.append("\n## Relevant Memories\n")
        for hit in memory_results:
            if total_chars >= char_limit:
                break
            title = hit.get("title", "Memory")
            text = hit.get("text", "").strip()[:500]
            memory_block = f"- **{title}**: {text}\n"
            context_parts.append(memory_block)
            total_chars += len(memory_block)

    # Output
    if not context_parts:
        print(f"No relevant context found for: {query}")
        return

    context = "\n".join(context_parts)

    if getattr(args, "json", False):
        output = {
            "query": query,
            "context": context,
            "code_results": len(code_results),
            "memory_results": len(memory_results),
            "total_chars": len(context),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"# Context for: {query}\n")
        print(context)
        print(
            f"\n---\n_Generated from {len(code_results)} code files and {len(memory_results)} memories_"
        )
