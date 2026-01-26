"""Reindex command for twin-mind."""

from typing import Any

from twin_mind.commands.index import cmd_index
from twin_mind.commands.reset import cmd_reset


def cmd_reindex(args: Any) -> None:
    """Reset code and reindex (convenience command)."""
    # Set up args for reset
    args.target = "code"
    args.force = True
    args.dry_run = False
    cmd_reset(args)

    # Set up args for index
    args.fresh = True
    args.dry_run = False
    args.status = False
    args.verbose = getattr(args, "verbose", False)
    cmd_index(args)
