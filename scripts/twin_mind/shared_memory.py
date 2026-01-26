"""Shared memory operations for twin-mind."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from twin_mind.fs import get_decisions_path
from twin_mind.git import get_git_author
from twin_mind.output import error


def write_shared_memory(message: str, tag: Optional[str] = None) -> bool:
    """Write a memory to the shared decisions.jsonl file."""
    decisions_path = get_decisions_path()

    entry = {
        "ts": datetime.now().isoformat(),
        "msg": message,
        "tag": tag or "general",
        "author": get_git_author(),
    }

    try:
        # Append to file (create if doesn't exist)
        with open(decisions_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(error(f"Failed to write shared memory: {e}"))
        return False


def read_shared_memories() -> List[Dict[str, Any]]:
    """Read all memories from decisions.jsonl."""
    decisions_path = get_decisions_path()
    memories = []

    if not decisions_path.exists():
        return memories

    try:
        with open(decisions_path, encoding="utf-8") as f:
            for _line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    memories.append(entry)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    pass
    except Exception:
        pass

    return memories


def search_shared_memories(query: str, top_k: int = 10) -> List[Tuple[int, Dict[str, Any]]]:
    """Search shared memories using simple text matching.

    Returns list of (score, entry) tuples sorted by relevance.
    """
    memories = read_shared_memories()
    if not memories:
        return []

    query_lower = query.lower()
    query_words = set(query_lower.split())
    results = []

    for entry in memories:
        msg = entry.get("msg", "").lower()
        tag = entry.get("tag", "").lower()

        # Simple scoring: count matching words + bonus for tag match
        score = 0
        for word in query_words:
            if word in msg:
                score += msg.count(word)
            if word in tag:
                score += 2  # Tag matches are more significant

        if score > 0:
            results.append((score, entry))

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_k]
