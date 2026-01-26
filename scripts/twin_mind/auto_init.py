"""Auto-initialization for twin-mind."""

from datetime import datetime
from pathlib import Path
from typing import Any

from twin_mind.config import get_config, get_extensions, get_skip_dirs
from twin_mind.constants import UNSAFE_DIRS
from twin_mind.fs import (
    create_gitignore,
    ensure_brain_dir,
    get_brain_dir,
    get_code_path,
    get_memory_path,
)
from twin_mind.git import get_current_commit, is_git_repo
from twin_mind.index_state import save_index_state
from twin_mind.indexing import collect_files, detect_language
from twin_mind.memvid_check import get_memvid_sdk
from twin_mind.output import error, info, success


def is_safe_directory() -> bool:
    """Check if current directory is safe for auto-initialization."""
    cwd = Path.cwd().resolve()
    cwd_str = str(cwd)

    # Don't init in home directory itself
    if cwd == Path.home():
        return False

    # Don't init in system directories
    for unsafe in UNSAFE_DIRS:
        if cwd_str == unsafe or cwd_str.startswith(unsafe + "/"):
            # Allow subdirectories of /tmp and home
            if unsafe == "/tmp" or cwd_str.startswith(str(Path.home())):
                continue
            return False

    return True


def has_code_files() -> bool:
    """Check if directory has indexable code files."""
    config = get_config()
    extensions = get_extensions(config)
    skip_dirs = get_skip_dirs(config)

    for item in Path.cwd().iterdir():
        if item.is_file() and item.suffix in extensions:
            return True
        if item.is_dir() and item.name not in skip_dirs:
            # Check one level deep
            for subitem in item.iterdir():
                if subitem.is_file() and subitem.suffix in extensions:
                    return True
    return False


def should_auto_init(command: str) -> bool:
    """Check if we should auto-initialize for this command."""
    # Commands that don't need auto-init
    no_init_commands = {"init", "uninstall", "help"}
    if command in no_init_commands:
        return False

    # Already initialized
    if get_brain_dir().exists():
        return False

    # Safety checks
    if not is_safe_directory():
        return False

    # Must have code files
    if not has_code_files():
        return False

    return True


def auto_init(args: Any) -> bool:
    """Perform automatic initialization. Returns True if successful."""
    memvid_sdk = get_memvid_sdk()

    print(f"\n{info('No twin-mind setup detected in this project.')}")
    print(f"   {info('Auto-initializing...')}")

    try:
        # Create directory and gitignore
        ensure_brain_dir()
        create_gitignore()

        # Create stores
        code_path = get_code_path()
        memory_path = get_memory_path()

        with memvid_sdk.use("basic", str(code_path), mode="create") as mem:
            pass
        print(f"   {success('+')} Created {code_path.name}")

        with memvid_sdk.use("basic", str(memory_path), mode="create") as mem:
            # Add init memory
            mem.put(
                title="Twin-Mind Initialized",
                text=f"Twin-Mind auto-initialized on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                uri="twin-mind://system/init",
                tags=["system", f"timestamp:{datetime.now().isoformat()}"],
            )
        print(f"   {success('+')} Created {memory_path.name}")

        # Index codebase
        print(f"   {info('Indexing codebase...')}")
        config = get_config()

        # Quick index
        files = collect_files(config)
        if files:
            with memvid_sdk.use("basic", str(code_path), mode="open") as mem:
                for file_path in files:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        rel_path = str(file_path.relative_to(Path.cwd()))
                        lang = detect_language(file_path.suffix)
                        mem.put(
                            title=rel_path,
                            text=content,
                            uri=f"file://{rel_path}",
                            tags=[lang, file_path.suffix.lstrip(".")],
                        )
                    except Exception:
                        pass

            # Save index state
            if is_git_repo():
                save_index_state(get_current_commit() or "", len(files))

        print(f"   {success('+')} Indexed {len(files)} files")
        print(f"   {success('Ready!')}\n")
        return True

    except Exception as e:
        print(f"   {error(f'Auto-init failed: {e}')}")
        return False
