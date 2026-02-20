"""Entity graph command for twin-mind."""

import json
import sys
from typing import Any, Dict, List

from twin_mind.entity_graph import (
    find_callees,
    find_callers,
    find_entities,
    find_subclasses,
)
from twin_mind.fs import get_entities_db_path


def _print_find_results(results: List[Dict[str, Any]]) -> None:
    for idx, result in enumerate(results, 1):
        print(
            f"[{idx}] [{result['kind']}] {result['qualname']}"
            f" (score: {result.get('score', 0):.2f})"
        )
        print(f"    {result['file_path']}:{result['line']}")


def _print_caller_results(results: List[Dict[str, Any]]) -> None:
    for idx, result in enumerate(results, 1):
        print(
            f"[{idx}] {result.get('caller')} -> {result.get('callee')}"
            f" [{result.get('caller_kind', 'unknown')}]"
        )
        print(f"    {result['file_path']}:{result['line']}")


def _print_callee_results(results: List[Dict[str, Any]]) -> None:
    for idx, result in enumerate(results, 1):
        print(f"[{idx}] {result.get('caller')} -> {result.get('callee')}")
        print(f"    {result['file_path']}:{result['line']}")


def _print_subclass_results(results: List[Dict[str, Any]]) -> None:
    for idx, result in enumerate(results, 1):
        print(f"[{idx}] {result.get('subclass')} inherits {result.get('base_class')}")
        print(f"    {result['file_path']}:{result['line']}")


def cmd_entities(args: Any) -> None:
    """Query extracted entities and relationships."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        print("Entity graph not found. Run: twin-mind index")
        sys.exit(1)

    action = getattr(args, "action", "")
    symbol = getattr(args, "symbol", "")
    limit = int(getattr(args, "limit", 20))
    emit_json = bool(getattr(args, "json", False))

    title = ""
    results: List[Dict[str, Any]]

    if action == "find":
        kind = getattr(args, "kind", None)
        results = find_entities(symbol, kind=kind, limit=limit)
        title = f"Entities matching: '{symbol}'"
    elif action == "callers":
        results = find_callers(symbol, limit=limit)
        title = f"Callers of: '{symbol}'"
    elif action == "callees":
        results = find_callees(symbol, limit=limit)
        title = f"Callees of: '{symbol}'"
    elif action == "inherits":
        results = find_subclasses(symbol, limit=limit)
        title = f"Subclasses of: '{symbol}'"
    else:
        print(f"Unknown entities action: {action}")
        sys.exit(1)

    if emit_json:
        print(
            json.dumps(
                {
                    "action": action,
                    "symbol": symbol,
                    "count": len(results),
                    "results": results,
                },
                indent=2,
            )
        )
        return

    if not results:
        print(f"No results for: '{symbol}'")
        return

    print(f"\n{title}\n")
    print("=" * 60)

    if action == "find":
        _print_find_results(results)
    elif action == "callers":
        _print_caller_results(results)
    elif action == "callees":
        _print_callee_results(results)
    elif action == "inherits":
        _print_subclass_results(results)
