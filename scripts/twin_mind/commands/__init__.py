"""Command implementations for twin-mind."""

from twin_mind.commands.ask import cmd_ask
from twin_mind.commands.context import cmd_context
from twin_mind.commands.doctor import cmd_doctor
from twin_mind.commands.export import cmd_export
from twin_mind.commands.index import cmd_index
from twin_mind.commands.init import cmd_init
from twin_mind.commands.install_skills import cmd_install_skills
from twin_mind.commands.prune import cmd_prune
from twin_mind.commands.recent import cmd_recent
from twin_mind.commands.reindex import cmd_reindex
from twin_mind.commands.remember import cmd_remember
from twin_mind.commands.reset import cmd_reset
from twin_mind.commands.search import cmd_search
from twin_mind.commands.stats import cmd_stats
from twin_mind.commands.status import cmd_status
from twin_mind.commands.uninstall import cmd_uninstall
from twin_mind.commands.upgrade import cmd_upgrade

__all__ = [
    "cmd_init",
    "cmd_index",
    "cmd_remember",
    "cmd_search",
    "cmd_ask",
    "cmd_recent",
    "cmd_stats",
    "cmd_status",
    "cmd_reset",
    "cmd_reindex",
    "cmd_prune",
    "cmd_context",
    "cmd_export",
    "cmd_doctor",
    "cmd_upgrade",
    "cmd_uninstall",
    "cmd_install_skills",
]
