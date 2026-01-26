"""Reindex command for twin-mind."""

from twin_mind.commands.reset import cmd_reset
from twin_mind.commands.index import cmd_index


def cmd_reindex(args):
    """Reset code and reindex (convenience command)."""
    # Set up args for reset
    args.target = 'code'
    args.force = True
    args.dry_run = False
    cmd_reset(args)

    # Set up args for index
    args.fresh = True
    args.dry_run = False
    args.status = False
    args.verbose = getattr(args, 'verbose', False)
    cmd_index(args)
