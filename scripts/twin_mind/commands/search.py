"""Search command for twin-mind."""

import json
from pathlib import Path

from twin_mind.config import get_config
from twin_mind.fs import get_code_path, get_memory_path
from twin_mind.index_state import check_stale_index
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.shared_memory import search_shared_memories


def cmd_search(args):
    """Search code, memory, or both."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()
    code_path = get_code_path()
    memory_path = get_memory_path()

    # Warn if code index is stale (when searching code)
    if args.scope in ('code', 'all') and code_path.exists():
        check_stale_index()

    # Check for --context and --full flags
    context_lines = getattr(args, 'context', None)
    show_full = getattr(args, 'full', False)

    # Adjust snippet size based on flags
    snippet_chars = 400
    if show_full:
        snippet_chars = 100000  # Get as much as possible
    elif context_lines:
        snippet_chars = max(400, context_lines * 200)

    # Check for adaptive retrieval setting
    use_adaptive = config["index"].get("adaptive_retrieval", True)
    # Allow command-line override
    if getattr(args, 'no_adaptive', False):
        use_adaptive = False

    results = []

    # Build find() kwargs based on adaptive setting
    def build_find_kwargs(top_k: int, snippet_chars: int) -> dict:
        kwargs = {'snippet_chars': snippet_chars}
        if use_adaptive:
            # Use adaptive retrieval - let memvid determine optimal count
            kwargs['adaptive'] = True
            kwargs['k'] = top_k  # max results as upper bound
        else:
            kwargs['k'] = top_k
        return kwargs

    find_kwargs = build_find_kwargs(args.top_k, snippet_chars)

    # Search code
    if args.scope in ('code', 'all') and code_path.exists():
        with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
            try:
                response = mem.find(args.query, **find_kwargs)
            except TypeError:
                # Fallback if memvid doesn't support adaptive parameter
                response = mem.find(args.query, k=args.top_k, snippet_chars=snippet_chars)
            for hit in response.get('hits', []):
                results.append(('code', hit))

    # Search local memory (memory.mv2)
    if args.scope in ('memory', 'all') and memory_path.exists():
        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            try:
                response = mem.find(args.query, **find_kwargs)
            except TypeError:
                # Fallback if memvid doesn't support adaptive parameter
                response = mem.find(args.query, k=args.top_k, snippet_chars=snippet_chars)
            for hit in response.get('hits', []):
                results.append(('memory', hit))

    # Search shared memories (decisions.jsonl)
    if args.scope in ('memory', 'all'):
        shared_results = search_shared_memories(args.query, top_k=args.top_k)
        for score, entry in shared_results:
            # Convert to hit-like format for consistency
            hit = {
                'title': f"[{entry.get('tag', 'general')}] {entry.get('msg', '')[:40]}...",
                'text': entry.get('msg', ''),
                'score': score / 10.0,  # Normalize score
                'uri': f"twin-mind://shared/{entry.get('ts', '')}",
                'tags': [f"category:{entry.get('tag', 'general')}", f"author:{entry.get('author', '')}"],
                'timestamp': entry.get('ts', '')
            }
            results.append(('shared', hit))

    # Sort by score and limit
    results.sort(key=lambda x: x[1].get('score', 0), reverse=True)
    results = results[:args.top_k]

    if not results:
        print(f"No results for: '{args.query}'")
        return

    # JSON output with enhanced metadata
    if args.json:
        output = {
            "query": args.query,
            "results": [],
            "meta": {
                "scope": args.scope,
                "total_results": len(results)
            }
        }
        for source, hit in results:
            result_obj = {
                "source": source,
                "file": hit.get('title', ''),
                "score": hit.get('score', 0),
                "uri": hit.get('uri', ''),
                "snippet": hit.get('text', '').strip()
            }
            # Try to extract line numbers from URI for code
            uri = hit.get('uri', '')
            if source == 'code' and uri and uri.startswith('twin-mind://code/'):
                result_obj["file_path"] = uri.replace('twin-mind://code/', '')
            output["results"].append(result_obj)
        print(json.dumps(output, indent=2))
        return

    print(f"\nResults for: '{args.query}' (in: {args.scope})\n")
    print("=" * 60)

    for i, (source, hit) in enumerate(results, 1):
        icon = "[code]" if source == 'code' else ("[shared]" if source == 'shared' else "[memory]")
        title = hit.get('title', 'untitled')

        print(f"\n{icon} [{i}] {title}")
        print(f"   Score: {hit.get('score', 0):.3f} | Source: {source}")
        print("-" * 40)

        # Get content to display
        content = hit.get('text', '').strip()

        # For code results with --full flag, try to read actual file
        uri = hit.get('uri', '')
        if source == 'code' and show_full and uri:
            file_path = uri.replace('file://', '')
            if Path(file_path).exists():
                try:
                    content = Path(file_path).read_text()
                    print(f"   [Full file: {file_path}]")
                except Exception:
                    pass  # Fall back to stored snippet

        # For code results with --context, show more lines
        if source == 'code' and context_lines and not show_full:
            # The snippet already has more chars, just show more lines
            lines = content.split('\n')
            max_lines = min(len(lines), context_lines * 2 + 10)
            content = '\n'.join(lines[:max_lines])

        # Display content
        if show_full:
            # Show full content with line numbers
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                print(f"   {line_num:4d} | {line}")
        else:
            # Show limited snippet
            max_chars = 300 if not context_lines else context_lines * 100
            max_lines = 8 if not context_lines else context_lines * 2
            snippet = content[:max_chars]
            indented = "\n".join(f"   {line}" for line in snippet.split("\n")[:max_lines])
            print(indented)
