"""Init command for twin-mind."""

from datetime import datetime
from typing import Any

from twin_mind.config import get_config
from twin_mind.fs import (
    create_gitignore,
    ensure_brain_dir,
    get_code_path,
    get_memory_path,
)
from twin_mind.indexing import get_memvid_create_kwargs
from twin_mind.memvid_check import check_memvid, get_memvid_sdk
from twin_mind.output import confirm, print_banner


def cmd_init(args: Any) -> None:
    """Initialize twin-mind (both stores)."""
    check_memvid()
    memvid_sdk = get_memvid_sdk()

    config = get_config()

    if args.banner:
        print_banner()

    code_path = get_code_path()
    memory_path = get_memory_path()

    if code_path.exists() or memory_path.exists():
        print("Twin-Mind already exists:")
        if code_path.exists():
            print(f"   {code_path}")
        if memory_path.exists():
            print(f"   {memory_path}")
        if not confirm("   Reinitialize?"):
            return

    ensure_brain_dir()
    create_gitignore()

    # Get memvid creation options
    create_kwargs = get_memvid_create_kwargs(config)

    embedding_model = config["index"].get("embedding_model")
    if embedding_model:
        print(f"   Using embedding model: {embedding_model}")

    # Initialize code store
    if code_path.exists():
        code_path.unlink()
    try:
        with memvid_sdk.use("basic", str(code_path), mode="create", **create_kwargs):
            pass  # Just create empty store
    except TypeError:
        # Fallback if memvid doesn't support model parameter
        with memvid_sdk.use("basic", str(code_path), mode="create"):
            pass

    # Initialize memory store with welcome message
    if memory_path.exists():
        memory_path.unlink()
    try:
        with memvid_sdk.use(
            "basic", str(memory_path), mode="create", **create_kwargs
        ) as memory_mem:
            init_msg = f"Twin-Mind initialized on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            memory_mem.put(
                title="Twin-Mind Initialized",
                text=init_msg,
                uri="twin-mind://system/init",
                tags=["system", f"timestamp:{datetime.now().isoformat()}"],
            )
    except TypeError:
        # Fallback if memvid doesn't support model parameter
        with memvid_sdk.use("basic", str(memory_path), mode="create") as memory_mem:
            init_msg = f"Twin-Mind initialized on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            memory_mem.put(
                title="Twin-Mind Initialized",
                text=init_msg,
                uri="twin-mind://system/init",
                tags=["system", f"timestamp:{datetime.now().isoformat()}"],
            )

    model_note = f" (model: {embedding_model})" if embedding_model else ""
    print(f"""
Twin-Mind initialized!{model_note}

   Code store:   {code_path}
   Memory store: {memory_path}

Next steps:
   twin-mind index      # Index your codebase
   twin-mind remember   # Save decisions/insights
""")
