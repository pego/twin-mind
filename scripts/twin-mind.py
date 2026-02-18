#!/usr/bin/env python3
"""
Twin-Mind - Dual memory layer for AI coding agents.
Separates codebase knowledge (resettable) from conversation memory (persistent).

Architecture:
    .claude/
    ├── code.mv2      # Codebase index - reset after refactors
    └── memory.mv2    # Decisions/insights - long-term persistent

Usage:
    twin-mind init
    twin-mind index [--fresh]
    twin-mind remember <message> [--tag TAG]
    twin-mind search <query> [--in code|memory|all]
    twin-mind ask <question>
    twin-mind recent [--n N]
    twin-mind stats
    twin-mind reset code|memory|all [--force]
    twin-mind prune memory [--before DATE] [--tag TAG]
    twin-mind export [--format md|json]
"""

import sys
from pathlib import Path

# Ensure the package directory is in the path so twin_mind can be imported
_package_dir = Path(__file__).parent
if str(_package_dir) not in sys.path:
    sys.path.insert(0, str(_package_dir))

from twin_mind.constants import VERSION  # noqa: E402 — single source of truth

if __name__ == "__main__":
    from twin_mind.cli import main

    main()
