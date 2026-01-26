"""File indexing logic for twin-mind."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from twin_mind.config import get_extensions, get_skip_dirs, parse_size
from twin_mind.output import ProgressBar, warning


def detect_language(ext: str) -> str:
    """Detect programming language from file extension."""
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".sql": "sql",
        ".sh": "bash",
        ".md": "markdown",
        ".yaml": "yaml",
        ".json": "json",
        ".html": "html",
        ".css": "css",
        ".vue": "vue",
        ".svelte": "svelte",
        ".graphql": "graphql",
        ".proto": "protobuf",
    }
    return lang_map.get(ext.lower(), "text")


def collect_files(config: Dict[str, Any]) -> List[Path]:
    """Collect all indexable files from current directory."""
    root = Path.cwd()
    extensions = get_extensions(config)
    skip_dirs = get_skip_dirs(config)
    max_size = parse_size(config["max_file_size"])

    files = []
    for item in root.rglob("*"):
        if item.is_file():
            parts = item.relative_to(root).parts
            if any(p.startswith(".") or p in skip_dirs for p in parts):
                continue
            if item.suffix.lower() in extensions:
                if item.stat().st_size <= max_size:
                    files.append(item)
    return files


def _read_file_content(filepath: Path, codebase_root: Path) -> Optional[Dict[str, Any]]:
    """Read a single file and prepare it for indexing. Returns None if file should be skipped."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        if not content.strip():
            return None

        relative_path = filepath.relative_to(codebase_root)
        return {
            "title": str(relative_path),
            "text": content,
            "uri": f"file://{relative_path}",
            "tags": [
                f"extension:{filepath.suffix}",
                f"language:{detect_language(filepath.suffix)}",
                f"indexed_at:{datetime.now().isoformat()}",
            ],
            "filepath": filepath,
        }
    except Exception:
        return None


def index_files_full(mem: Any, config: Dict[str, Any], args: Any) -> int:
    """Full reindex of all files."""
    codebase_root = Path.cwd()
    get_extensions(config)
    get_skip_dirs(config)
    parse_size(config["max_file_size"])
    verbose = config["output"]["verbose"] or getattr(args, "verbose", False)
    use_parallel = config["index"].get("parallel", True)
    num_workers = config["index"].get("parallel_workers", 4)

    print(f"Scanning: {codebase_root}")
    files = collect_files(config)
    print(f"   Found {len(files)} files")

    if not files:
        print(warning("   No indexable files found!"))
        return 0

    progress = ProgressBar(len(files), prefix="Indexing: ")
    indexed = 0

    # Use parallel file reading for better performance
    if use_parallel and len(files) > 10:
        print(f"   Using parallel ingestion ({num_workers} workers)...")
        file_data_list = []

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_read_file_content, fp, codebase_root): fp for fp in files}

            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    data = future.result()
                    if data:
                        file_data_list.append(data)
                except Exception as e:
                    if verbose:
                        print(warning(f"   Skip {filepath}: {e}"))
                progress.update()

        progress.finish()

        # Now batch insert into memvid
        print(f"   Committing {len(file_data_list)} files to index...")
        for data in file_data_list:
            try:
                mem.put(title=data["title"], text=data["text"], uri=data["uri"], tags=data["tags"])
                indexed += 1
                if verbose:
                    print(f"   + {data['title']}")
            except Exception as e:
                if verbose:
                    print(warning(f"   Failed to index {data['title']}: {e}"))
    else:
        # Sequential processing for small file sets
        for filepath in files:
            try:
                relative_path = filepath.relative_to(codebase_root)
                content = filepath.read_text(encoding="utf-8", errors="ignore")

                if not content.strip():
                    progress.update()
                    continue

                mem.put(
                    title=str(relative_path),
                    text=content,
                    uri=f"file://{relative_path}",
                    tags=[
                        f"extension:{filepath.suffix}",
                        f"language:{detect_language(filepath.suffix)}",
                        f"indexed_at:{datetime.now().isoformat()}",
                    ],
                )
                indexed += 1

                if verbose:
                    print(f"   + {relative_path}")

            except Exception as e:
                if verbose:
                    print(warning(f"   Skip {filepath}: {e}"))

            progress.update()

        progress.finish()

    return indexed


def index_files_incremental(
    mem: Any, changed_files: List[str], config: Dict[str, Any], args: Any
) -> int:
    """Incremental reindex of changed files only."""
    codebase_root = Path.cwd()
    extensions = get_extensions(config)
    max_size = parse_size(config["max_file_size"])
    verbose = config["output"]["verbose"] or getattr(args, "verbose", False)

    indexed = 0

    for rel_path in changed_files:
        filepath = codebase_root / rel_path

        if not filepath.exists():
            continue

        if filepath.suffix.lower() not in extensions:
            continue

        if filepath.stat().st_size > max_size:
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue

            mem.put(
                title=rel_path,
                text=content,
                uri=f"file://{rel_path}",
                tags=[
                    f"extension:{filepath.suffix}",
                    f"language:{detect_language(filepath.suffix)}",
                    f"indexed_at:{datetime.now().isoformat()}",
                ],
            )
            indexed += 1

            if verbose:
                print(f"   + {rel_path}")

        except Exception as e:
            if verbose:
                print(warning(f"   Skip {rel_path}: {e}"))

    return indexed


def get_memvid_create_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build kwargs for memvid store creation based on config."""
    kwargs = {}

    embedding_model = config["index"].get("embedding_model")
    if embedding_model:
        kwargs["model"] = embedding_model

    return kwargs
