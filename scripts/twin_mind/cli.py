"""Main CLI entry point for twin-mind."""

import argparse
import sys

from twin_mind.auto_init import auto_init, should_auto_init
from twin_mind.commands import (
    cmd_ask,
    cmd_context,
    cmd_doctor,
    cmd_entities,
    cmd_export,
    cmd_index,
    cmd_init,
    cmd_install_skills,  # may be None on partial upgrades — handled below
    cmd_prune,
    cmd_recent,
    cmd_reindex,
    cmd_remember,
    cmd_reset,
    cmd_search,
    cmd_stats,
    cmd_status,
    cmd_uninstall,
    cmd_upgrade,
)
from twin_mind.constants import VERSION
from twin_mind.output import Colors


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="twin-mind",
        description="Twin-Mind - Dual memory for AI coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  twin-mind init                          # Initialize
  twin-mind index --fresh                 # Reindex codebase from scratch
  twin-mind remember "Chose JWT" -t arch  # Save a decision
  twin-mind search "auth" --in code       # Search only code
  twin-mind ask "How does caching work?"  # Query everything
  twin-mind reset code                    # Reset code after refactor
  twin-mind export --format md -o mem.md  # Export memories
  twin-mind stats                         # Show statistics

Repository: https://github.com/pego/twin-mind
""",
    )

    parser.add_argument("--version", "-V", action="version", version=f"twin-mind {VERSION}")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize twin-mind")
    p_init.add_argument("--banner", "-b", action="store_true", help="Show ASCII banner")

    # index
    p_index = subparsers.add_parser("index", help="Index codebase")
    p_index.add_argument(
        "--fresh", "-f", action="store_true", help="Delete existing index and rebuild from scratch"
    )
    p_index.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Preview what would be indexed without executing",
    )
    p_index.add_argument("--dry-run", action="store_true", help="Same as --status")
    p_index.add_argument(
        "--verbose", "-v", action="store_true", help="Show each file as it is processed"
    )

    # remember
    p_remember = subparsers.add_parser("remember", help="Store a memory")
    p_remember.add_argument("message", help="What to remember")
    p_remember.add_argument("--tag", "-t", help="Category tag (arch, bugfix, feature, etc.)")
    p_remember_dest = p_remember.add_mutually_exclusive_group()
    p_remember_dest.add_argument(
        "--local", action="store_true", help="Force save to local memory.mv2 (not shared)"
    )
    p_remember_dest.add_argument(
        "--share", action="store_true", help="Force save to shared decisions.jsonl"
    )

    # search
    p_search = subparsers.add_parser("search", help="Search twin-mind")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument(
        "--in",
        dest="scope",
        choices=["code", "memory", "entities", "all"],
        default="all",
        help="Where to search (default: all)",
    )
    p_search.add_argument("--top-k", "-k", type=int, default=10, help="Number of results")
    p_search.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    p_search.add_argument(
        "--context", "-c", type=int, metavar="N", help="Show N lines before/after each match"
    )
    p_search.add_argument(
        "--full", action="store_true", help="Show full file content for code matches"
    )
    p_search.add_argument(
        "--no-adaptive", action="store_true", help="Disable adaptive retrieval (use fixed top-k)"
    )
    p_search.add_argument(
        "--scope", dest="dir_scope", metavar="PATH",
        help="Limit code search to a subdirectory (e.g., src/auth/)",
    )

    # ask
    p_ask = subparsers.add_parser("ask", help="Ask a question")
    p_ask.add_argument("question", help="Your question")

    # recent
    p_recent = subparsers.add_parser("recent", help="Show recent memories")
    p_recent.add_argument("--n", type=int, default=10, help="Number to show")

    # stats
    subparsers.add_parser("stats", help="Show twin-mind statistics")

    # status
    subparsers.add_parser("status", help="Show twin-mind health status")

    # reindex
    p_reindex = subparsers.add_parser("reindex", help="Reset code and reindex fresh")
    p_reindex.add_argument("--verbose", "-v", action="store_true", help="Show each file")

    # reset
    p_reset = subparsers.add_parser("reset", help="Reset a memory store")
    p_reset.add_argument("target", choices=["code", "memory", "all"], help="What to reset")
    p_reset.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    p_reset.add_argument("--dry-run", action="store_true", help="Preview without executing")

    # prune
    p_prune = subparsers.add_parser("prune", help="Prune old memories")
    p_prune.add_argument("target", choices=["memory"], help="What to prune")
    p_prune.add_argument("--before", "-b", help="Remove before date (YYYY-MM-DD, 30d, 2w)")
    p_prune.add_argument("--tag", "-t", help="Remove by tag")
    p_prune.add_argument("--dry-run", action="store_true", help="Preview without executing")
    p_prune.add_argument("--force", action="store_true", help="Skip confirmation")

    # context
    p_context = subparsers.add_parser("context", help="Generate combined context for prompts")
    p_context.add_argument("query", help="Query to build context for")
    p_context.add_argument(
        "--max-tokens",
        "-m",
        type=int,
        default=4000,
        help="Maximum tokens for context (default: 4000)",
    )
    p_context.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # entities (hidden on partial upgrades where module is missing)
    if cmd_entities is not None:
        p_entities = subparsers.add_parser("entities", help="Query extracted code entities")
        p_entities_sub = p_entities.add_subparsers(dest="action")
        p_entities_sub.required = True

        p_entities_find = p_entities_sub.add_parser("find", help="Find entities by symbol")
        p_entities_find.add_argument("symbol", help="Entity symbol or qualified name")
        p_entities_find.add_argument(
            "--kind",
            choices=["module", "class", "function", "method"],
            help="Filter by entity kind",
        )
        p_entities_find.add_argument("--limit", "-k", type=int, default=10, help="Max results")
        p_entities_find.add_argument("--json", "-j", action="store_true", help="Output as JSON")

        p_entities_callers = p_entities_sub.add_parser("callers", help="Find callers of a symbol")
        p_entities_callers.add_argument("symbol", help="Symbol to inspect")
        p_entities_callers.add_argument("--limit", "-k", type=int, default=20, help="Max results")
        p_entities_callers.add_argument("--json", "-j", action="store_true", help="Output as JSON")

        p_entities_callees = p_entities_sub.add_parser("callees", help="Find callees for a symbol")
        p_entities_callees.add_argument("symbol", help="Caller symbol to inspect")
        p_entities_callees.add_argument("--limit", "-k", type=int, default=20, help="Max results")
        p_entities_callees.add_argument("--json", "-j", action="store_true", help="Output as JSON")

        p_entities_inherits = p_entities_sub.add_parser("inherits", help="Find subclasses")
        p_entities_inherits.add_argument("symbol", help="Base class symbol")
        p_entities_inherits.add_argument("--limit", "-k", type=int, default=20, help="Max results")
        p_entities_inherits.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # export
    p_export = subparsers.add_parser("export", help="Export memories")
    p_export.add_argument(
        "--format", "-f", choices=["md", "json"], default="md", help="Output format"
    )
    p_export.add_argument("--output", "-o", help="Output file (default: stdout)")

    # uninstall
    p_uninstall = subparsers.add_parser("uninstall", help="Remove twin-mind installation")
    p_uninstall.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Run diagnostics and maintenance")
    p_doctor.add_argument(
        "--vacuum", action="store_true", help="Reclaim space from deleted entries"
    )
    p_doctor.add_argument(
        "--rebuild", action="store_true", help="Rebuild indexes (recommended after >20%% deletions)"
    )

    # install-skills (omitted on partial upgrades where the module is missing)
    if cmd_install_skills is not None:
        p_install_skills = subparsers.add_parser(
            "install-skills", help="Symlink twin-mind skill into all detected AI coding agents"
        )
        p_install_skills.add_argument(
            "--dry-run", action="store_true", help="Preview without making changes"
        )
        p_install_skills.add_argument(
            "--update", action="store_true", help="Re-download SKILL.md before installing"
        )

    # upgrade
    p_upgrade = subparsers.add_parser("upgrade", help="Check for updates and upgrade twin-mind")
    p_upgrade.add_argument(
        "--check", "-c", action="store_true", help="Only check for updates, do not install"
    )
    p_upgrade.add_argument(
        "--force", "-f", action="store_true", help="Upgrade without confirmation prompt"
    )

    args = parser.parse_args()

    # Handle --no-color flag globally
    if args.no_color:
        Colors.disable()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "index": cmd_index,
        "remember": cmd_remember,
        "search": cmd_search,
        "ask": cmd_ask,
        "recent": cmd_recent,
        "stats": cmd_stats,
        "status": cmd_status,
        "reindex": cmd_reindex,
        "reset": cmd_reset,
        "prune": cmd_prune,
        "context": cmd_context,
        **({"entities": cmd_entities} if cmd_entities is not None else {}),
        "export": cmd_export,
        "uninstall": cmd_uninstall,
        "doctor": cmd_doctor,
        "upgrade": cmd_upgrade,
        **({"install-skills": cmd_install_skills} if cmd_install_skills is not None else {}),
    }

    # Auto-init for commands that need it
    if should_auto_init(args.command):
        if not auto_init(args):
            sys.exit(1)

    commands[args.command](args)


if __name__ == "__main__":
    main()
