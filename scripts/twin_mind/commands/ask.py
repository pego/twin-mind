"""Ask command for twin-mind."""

from twin_mind.commands.search import cmd_search


def cmd_ask(args):
    """Ask a question (searches both stores)."""
    args.scope = 'all'
    args.top_k = 5
    args.json = False
    args.query = args.question
    cmd_search(args)
