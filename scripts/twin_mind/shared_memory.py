"""Shared memory operations for twin-mind."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from twin_mind.fs import FileLock, get_decisions_mv2_path, get_decisions_path
from twin_mind.git import get_git_author
from twin_mind.memvid_check import get_memvid_sdk
from twin_mind.output import error


def _append_jsonl_atomic(path: Any, line: str) -> None:
    """Append one JSONL line under a process lock and flush to disk."""
    with FileLock(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())


def write_shared_memory(message: str, tag: Optional[str] = None) -> bool:
    """Write a memory to the shared decisions.jsonl file."""
    decisions_path = get_decisions_path()
    decisions_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now().isoformat(),
        "msg": message,
        "tag": tag or "general",
        "author": get_git_author(),
    }

    try:
        _append_jsonl_atomic(decisions_path, json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(error(f"Failed to write shared memory: {e}"))
        return False

    # Incrementally update MV2 index if it already exists (best-effort)
    mv2_path = get_decisions_mv2_path()
    if mv2_path.exists():
        try:
            with FileLock(mv2_path):
                memvid_sdk = get_memvid_sdk()
                with memvid_sdk.use("basic", str(mv2_path), mode="open") as mem:
                    mem.put(
                        title=f"[{entry.get('tag', 'general')}] {entry.get('msg', '')[:50]}",
                        text=entry.get("msg", ""),
                        uri=f"twin-mind://shared/{entry.get('ts', '')}",
                        tags=[
                            f"category:{entry.get('tag', 'general')}",
                            f"author:{entry.get('author', '')}",
                        ],
                    )
        except Exception:
            pass  # MV2 update is best-effort; JSONL is the source of truth

    return True


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


def build_decisions_index() -> bool:
    """Build (or rebuild) decisions.mv2 from decisions.jsonl.

    Returns True if the index was successfully created.
    """
    memories = read_shared_memories()
    if not memories:
        return False
    try:
        memvid_sdk = get_memvid_sdk()
        mv2_path = get_decisions_mv2_path()
        with FileLock(mv2_path):
            with memvid_sdk.use("basic", str(mv2_path), mode="create") as mem:
                for entry in memories:
                    mem.put(
                        title=f"[{entry.get('tag', 'general')}] {entry.get('msg', '')[:50]}",
                        text=entry.get("msg", ""),
                        uri=f"twin-mind://shared/{entry.get('ts', '')}",
                        tags=[
                            f"category:{entry.get('tag', 'general')}",
                            f"author:{entry.get('author', '')}",
                        ],
                    )
        return True
    except Exception:
        return False


def _search_decisions_semantic(query: str, top_k: int) -> List[Tuple[float, Dict[str, Any]]]:
    """Search decisions using semantic MV2 index.

    Returns list of (score, entry) tuples.
    """
    mv2_path = get_decisions_mv2_path()
    try:
        memvid_sdk = get_memvid_sdk()
        with memvid_sdk.use("basic", str(mv2_path), mode="open") as mem:
            response = mem.find(query, k=top_k)
        results = []
        for hit in response.get("hits", []):
            score = hit.get("score", 0.0)
            # Reconstruct a decisions-style entry from the hit
            entry = {
                "msg": hit.get("text", ""),
                "tag": "general",
                "ts": "",
                "author": "",
            }
            # Extract tag/author from stored tags list
            for t in hit.get("tags", []):
                if t.startswith("category:"):
                    entry["tag"] = t[len("category:"):]
                elif t.startswith("author:"):
                    entry["author"] = t[len("author:"):]
            # Extract ts from URI
            uri = hit.get("uri", "")
            if uri.startswith("twin-mind://shared/"):
                entry["ts"] = uri[len("twin-mind://shared/"):]
            results.append((score, entry))
        return results
    except Exception:
        return []


def _search_decisions_text(query: str, top_k: int) -> List[Tuple[int, Dict[str, Any]]]:
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


def search_shared_memories(query: str, top_k: int = 10) -> List[Tuple[Any, Dict[str, Any]]]:
    """Search shared memories, using semantic search when available.

    Uses MV2 semantic index if it exists. If JSONL exists but MV2 doesn't,
    lazily builds the index and uses semantic search. Falls back to text matching.

    Returns list of (score, entry) tuples sorted by relevance.
    """
    mv2_path = get_decisions_mv2_path()
    jsonl_path = get_decisions_path()

    # Semantic search path
    if mv2_path.exists():
        return _search_decisions_semantic(query, top_k)

    # Lazy build: JSONL exists but no MV2 yet
    if jsonl_path.exists() and read_shared_memories():
        if build_decisions_index():
            return _search_decisions_semantic(query, top_k)

    # Fallback: text matching
    return _search_decisions_text(query, top_k)
