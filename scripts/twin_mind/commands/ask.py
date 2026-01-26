"""Ask command for twin-mind."""

from typing import Any

from twin_mind.commands.search import cmd_search


def cmd_ask(args: Any) -> None:
    """Ask a question (searches both stores)."""
    args.scope = "all"
    args.top_k = 5
    args.json = False
    args.query = args.question
    cmd_search(args)
