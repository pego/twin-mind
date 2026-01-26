"""Configuration loading for twin-mind."""

import copy
import json
from pathlib import Path

from twin_mind.constants import (
    BRAIN_DIR,
    DEFAULT_CONFIG,
    CODE_EXTENSIONS,
    SKIP_DIRS,
)
from twin_mind.output import warning


def parse_size(size_str: str) -> int:
    """Parse size string like '500KB' to bytes."""
    size_str = str(size_str).strip().upper()
    # Check longer suffixes first to avoid 'B' matching before 'KB'
    multipliers = [('GB', 1024**3), ('MB', 1024*1024), ('KB', 1024), ('B', 1)]
    for suffix, mult in multipliers:
        if size_str.endswith(suffix):
            return int(float(size_str[:-len(suffix)]) * mult)
    return int(size_str)


def load_config() -> dict:
    """Load twin-mind config from .claude/settings.json."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    settings_path = Path.cwd() / BRAIN_DIR / "settings.json"

    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            if "twin-mind" in settings:
                user_config = settings["twin-mind"]
                # Merge extensions
                if "extensions" in user_config:
                    if "include" in user_config["extensions"]:
                        config["extensions"]["include"] = user_config["extensions"]["include"]
                    if "exclude" in user_config["extensions"]:
                        config["extensions"]["exclude"] = user_config["extensions"]["exclude"]
                # Merge skip_dirs
                if "skip_dirs" in user_config:
                    config["skip_dirs"] = user_config["skip_dirs"]
                # Other settings
                if "max_file_size" in user_config:
                    config["max_file_size"] = user_config["max_file_size"]
                if "index" in user_config:
                    config["index"].update(user_config["index"])
                if "output" in user_config:
                    config["output"].update(user_config["output"])
                if "memory" in user_config:
                    config["memory"].update(user_config["memory"])
                # Legacy support: share_memories at top level
                if "share_memories" in user_config:
                    config["memory"]["share_memories"] = user_config["share_memories"]
                # Legacy support: embedding_model at top level
                if "embedding_model" in user_config:
                    config["index"]["embedding_model"] = user_config["embedding_model"]
        except (json.JSONDecodeError, IOError) as e:
            print(warning(f"Config parse error: {e}. Using defaults."))

    return config


def get_extensions(config: dict) -> set:
    """Get final set of extensions to index."""
    extensions = CODE_EXTENSIONS.copy()
    for ext in config["extensions"]["include"]:
        extensions.add(ext if ext.startswith('.') else f'.{ext}')
    for ext in config["extensions"]["exclude"]:
        extensions.discard(ext if ext.startswith('.') else f'.{ext}')
    return extensions


def get_skip_dirs(config: dict) -> set:
    """Get final set of directories to skip."""
    skip = SKIP_DIRS.copy()
    for d in config["skip_dirs"]:
        skip.add(d)
    return skip


# Global config (loaded once)
_config_cache = None


def get_config() -> dict:
    """Get cached config."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache
