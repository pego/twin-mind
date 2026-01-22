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
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import re
import json

try:
    import memvid_sdk
    MEMVID_AVAILABLE = True
    MEMVID_IMPORT_ERROR = None
except ImportError as e:
    MEMVID_AVAILABLE = False
    MEMVID_IMPORT_ERROR = str(e)


# === Output Helpers ===
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    BOLD = "\033[1m"

    _enabled = True

    @classmethod
    def disable(cls):
        cls.RESET = cls.RED = cls.GREEN = ""
        cls.YELLOW = cls.BLUE = cls.BOLD = ""
        cls._enabled = False

    @classmethod
    def is_enabled(cls):
        return cls._enabled


def supports_color() -> bool:
    """Check if terminal supports color output."""
    if os.environ.get('NO_COLOR'):
        return False
    if not hasattr(sys.stdout, 'isatty'):
        return False
    return sys.stdout.isatty()


def color(text: str, color_code: str) -> str:
    """Wrap text in color code."""
    if not Colors._enabled:
        return text
    return f"{color_code}{text}{Colors.RESET}"


def success(msg: str) -> str:
    return color(msg, Colors.GREEN)


def warning(msg: str) -> str:
    return color(msg, Colors.YELLOW)


def error(msg: str) -> str:
    return color(msg, Colors.RED)


def info(msg: str) -> str:
    return color(msg, Colors.BLUE)


# === Configuration ===
BRAIN_DIR = ".claude"
CODE_FILE = "code.mv2"
MEMORY_FILE = "memory.mv2"
VERSION = "1.1.0"

CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.kt', '.scala',
    '.go', '.rs', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php',
    '.swift', '.sql', '.sh', '.bash', '.yaml', '.yml', '.json',
    '.toml', '.xml', '.html', '.css', '.scss', '.md', '.txt', '.vue',
    '.svelte', '.astro', '.prisma', '.graphql', '.proto', '.tf'
}

SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    '.idea', '.vscode', 'dist', 'build', 'target', '.next', '.nuxt',
    'coverage', '.pytest_cache', '.mypy_cache', 'vendor', '.claude',
    '.terraform', '.serverless', 'cdk.out', '.aws-sam'
}

MAX_FILE_SIZE = 500 * 1024  # 500KB

# Default config (can be overridden via .claude/settings.json)
DEFAULT_CONFIG = {
    "extensions": {
        "include": [],
        "exclude": []
    },
    "skip_dirs": [],
    "max_file_size": "500KB",
    "index": {
        "auto_incremental": True,
        "track_deletions": True
    },
    "output": {
        "color": True,
        "verbose": False
    }
}


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
    import copy
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
        except (json.JSONDecodeError, IOError) as e:
            print(warning(f"⚠️  Config parse error: {e}. Using defaults."))

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


def parse_timeline_entry(entry: dict) -> dict:
    """Parse a timeline entry's preview field into structured data.

    Timeline entries have format:
        preview: "text content\ntitle: Title\nuri: URI\ntags: tag1,tag2"

    Returns dict with: title, text, uri, tags
    """
    preview = entry.get('preview', '')
    uri = entry.get('uri', '')

    # Default values
    result = {
        'title': 'untitled',
        'text': preview,
        'uri': uri or '',
        'tags': [],
        'timestamp': entry.get('timestamp', 0),
        'frame_id': entry.get('frame_id', '')
    }

    # Parse embedded metadata from preview
    lines = preview.split('\n')
    text_lines = []

    for line in lines:
        if line.startswith('title: '):
            result['title'] = line[7:]
        elif line.startswith('uri: '):
            if not result['uri']:
                result['uri'] = line[5:]
        elif line.startswith('tags: '):
            tags_str = line[6:]
            if tags_str:
                result['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
        else:
            text_lines.append(line)

    result['text'] = '\n'.join(text_lines).strip()
    return result


# Global config (loaded once)
_config_cache = None


def get_config() -> dict:
    """Get cached config."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


# === File Locking ===
import time

if sys.platform == 'win32':
    import msvcrt
    def _lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    def _unlock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl
    def _lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    def _unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class FileLock:
    """Simple file-based lock with timeout."""

    def __init__(self, path: Path, timeout: int = 5):
        self.lock_path = Path(str(path) + '.lock')
        self.timeout = timeout
        self._lock_file = None

    def acquire(self) -> bool:
        """Acquire lock, return True if successful."""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # Check for stale lock (>60s old)
                if self.lock_path.exists():
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > 60:
                        self.lock_path.unlink()

                self._lock_file = open(self.lock_path, 'w')
                _lock_file(self._lock_file)
                self._lock_file.write(str(os.getpid()))
                self._lock_file.flush()
                return True
            except (IOError, OSError):
                time.sleep(0.1)
        return False

    def release(self):
        """Release the lock."""
        if self._lock_file:
            try:
                _unlock_file(self._lock_file)
                self._lock_file.close()
                if self.lock_path.exists():
                    self.lock_path.unlink()
            except (IOError, OSError):
                pass
            self._lock_file = None

    def __enter__(self):
        if not self.acquire():
            raise IOError(f"Could not acquire lock on {self.lock_path} (timeout {self.timeout}s)")
        return self

    def __exit__(self, *args):
        self.release()


# === Progress ===
class ProgressBar:
    """Simple progress bar for terminal."""

    def __init__(self, total: int, width: int = 30, prefix: str = ""):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self._is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    def update(self, n: int = 1):
        self.current += n
        if self._is_tty:
            self._render()

    def _render(self):
        pct = self.current / self.total if self.total > 0 else 1
        filled = int(self.width * pct)
        bar = '=' * filled + '>' + ' ' * (self.width - filled - 1)
        line = f"\r{self.prefix}[{bar}] {self.current}/{self.total} ({pct*100:.0f}%)"
        sys.stdout.write(line)
        sys.stdout.flush()

    def finish(self):
        if self._is_tty:
            sys.stdout.write('\n')
            sys.stdout.flush()


# === Git Integration ===
import subprocess


def is_git_repo() -> bool:
    """Check if current directory is a git repo."""
    try:
        subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True, check=True, cwd=Path.cwd()
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_current_commit() -> str | None:
    """Get current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_changed_files(since_commit: str) -> tuple[list[str], list[str]]:
    """Get changed and deleted files since a commit.

    Returns: (changed_files, deleted_files)
    """
    changed = []
    deleted = []

    try:
        # Changed/added files
        result = subprocess.run(
            ['git', 'diff', '--name-only', since_commit, 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        changed = [f for f in result.stdout.strip().split('\n') if f]

        # Deleted files
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=D', since_commit, 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        deleted = [f for f in result.stdout.strip().split('\n') if f]

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return changed, deleted


def get_commits_behind(since_commit: str) -> int:
    """Get number of commits between since_commit and HEAD."""
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'{since_commit}..HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return -1


def get_branch_name() -> str:
    """Get current branch name."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=Path.cwd()
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


# === Index State ===
INDEX_STATE_FILE = "index-state.json"


def get_index_state_path() -> Path:
    return Path.cwd() / BRAIN_DIR / INDEX_STATE_FILE


def load_index_state() -> dict | None:
    """Load index state from file."""
    state_path = get_index_state_path()
    if not state_path.exists():
        return None
    try:
        with open(state_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_index_state(commit: str, file_count: int):
    """Save index state to file."""
    state = {
        "last_commit": commit,
        "indexed_at": datetime.now().isoformat(),
        "file_count": file_count
    }
    state_path = get_index_state_path()
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)


def get_index_age() -> str | None:
    """Get human-readable index age."""
    state = load_index_state()
    if not state or "indexed_at" not in state:
        return None

    try:
        indexed_at = datetime.fromisoformat(state["indexed_at"])
        delta = datetime.now() - indexed_at

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"
    except (ValueError, KeyError):
        return None


def check_stale_index(quiet: bool = False) -> bool:
    """Check if index is stale and optionally print warning.

    Returns True if index is stale (or missing).
    """
    if not is_git_repo():
        return False  # Can't determine staleness without git

    state = load_index_state()
    if not state or "last_commit" not in state:
        if not quiet:
            print(warning("⚠️  No index state found. Run: twin-mind index"))
        return True

    last_commit = state["last_commit"]
    commits_behind = get_commits_behind(last_commit)

    if commits_behind > 0:
        if not quiet:
            print(warning(f"⚠️  Index may be stale ({commits_behind} commits behind)"))
            print("   Run: twin-mind index")
        return True

    return False


# === Helpers ===

def check_memvid():
    if not MEMVID_AVAILABLE:
        print("❌ memvid-sdk not installed or import failed.")
        print(f"   Python: {sys.executable}")
        print(f"   Error: {MEMVID_IMPORT_ERROR}")
        print("   Run: pip install memvid-sdk --break-system-packages")
        sys.exit(1)


def get_brain_dir() -> Path:
    return Path.cwd() / BRAIN_DIR


def get_code_path() -> Path:
    return get_brain_dir() / CODE_FILE


def get_memory_path() -> Path:
    return get_brain_dir() / MEMORY_FILE


def ensure_brain_dir():
    get_brain_dir().mkdir(parents=True, exist_ok=True)


def detect_language(ext: str) -> str:
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'typescript', '.jsx': 'javascript', '.java': 'java',
        '.go': 'go', '.rs': 'rust', '.c': 'c', '.cpp': 'cpp',
        '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.sh': 'bash',
        '.md': 'markdown', '.yaml': 'yaml', '.json': 'json',
        '.html': 'html', '.css': 'css', '.vue': 'vue',
        '.svelte': 'svelte', '.graphql': 'graphql', '.proto': 'protobuf'
    }
    return lang_map.get(ext.lower(), 'text')


def format_size(bytes_size: int) -> str:
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024*1024):.2f} MB"


def confirm(message: str) -> bool:
    response = input(f"{message} [y/N]: ").strip().lower()
    return response == 'y'


def print_banner():
    banner = r"""
  ______         _          __  __ _           _
 |__  __|       (_)        |  \/  (_)         | |
    | |_      __ _ _ __    | \  / |_ _ __   __| |
    | \ \ /\ / / | '_ \   | |\/| | | '_ \ / _` |
    | |\ V  V /| | | | |  | |  | | | | | | (_| |
    |_| \_/\_/ |_|_| |_|  |_|  |_|_|_| |_|\__,_|

    Dual Memory for AI Coding Agents v{version}
    """
    print(banner.format(version=VERSION))


# === Commands ===

def cmd_init(args):
    """Initialize twin-mind (both stores)."""
    check_memvid()

    if args.banner:
        print_banner()

    code_path = get_code_path()
    memory_path = get_memory_path()

    if code_path.exists() or memory_path.exists():
        print("⚠️  Twin-Mind already exists:")
        if code_path.exists():
            print(f"   📄 {code_path}")
        if memory_path.exists():
            print(f"   📝 {memory_path}")
        if not confirm("   Reinitialize?"):
            return

    ensure_brain_dir()

    # Initialize code store
    if code_path.exists():
        code_path.unlink()
    with memvid_sdk.use('basic', str(code_path), mode='create') as code_mem:
        pass  # Just create empty store

    # Initialize memory store with welcome message
    if memory_path.exists():
        memory_path.unlink()
    with memvid_sdk.use('basic', str(memory_path), mode='create') as memory_mem:
        init_msg = f"Twin-Mind initialized on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        memory_mem.put(
            title="Twin-Mind Initialized",
            text=init_msg,
            uri="twin-mind://system/init",
            tags=["system", f"timestamp:{datetime.now().isoformat()}"]
        )

    print(f"""
✅ Twin-Mind initialized!

   📄 Code store:   {code_path}
   📝 Memory store: {memory_path}

Next steps:
   twin-mind index      # Index your codebase
   twin-mind remember   # Save decisions/insights
""")


def cmd_index(args):
    """Index codebase into code store."""
    check_memvid()

    config = get_config()
    code_path = get_code_path()

    # Initialize colors based on config
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    if not get_brain_dir().exists():
        print(error("❌ Twin-Mind not initialized. Run: twin-mind init"))
        sys.exit(1)

    # Determine indexing mode
    incremental = False
    changed_files = []
    deleted_files = []
    state = load_index_state()

    if args.fresh:
        # Fresh index requested
        if code_path.exists():
            print(info("🔄 Fresh index requested, resetting code store..."))
            code_path.unlink()
    elif state and is_git_repo():
        # Try incremental
        last_commit = state.get("last_commit")
        if last_commit:
            commits_behind = get_commits_behind(last_commit)
            if commits_behind == 0:
                print(success("✅ Index is up to date (no new commits)"))
                return
            elif commits_behind > 0:
                changed_files, deleted_files = get_changed_files(last_commit)
                if changed_files or deleted_files:
                    incremental = True
                    print(info(f"📂 Incremental index (since {last_commit[:7]})"))
                    print(f"   Changed: {len(changed_files)} files")
                    print(f"   Deleted: {len(deleted_files)} files")
                else:
                    print(success("✅ Index is up to date"))
                    return

    # Dry run mode
    if getattr(args, 'dry_run', False) or getattr(args, 'status', False):
        if incremental:
            print("\n   Would reindex:")
            for f in changed_files[:10]:
                print(f"   + {f}")
            if len(changed_files) > 10:
                print(f"   ... and {len(changed_files) - 10} more")
        else:
            codebase_root = Path.cwd()
            extensions = get_extensions(config)
            skip_dirs = get_skip_dirs(config)
            max_size = parse_size(config["max_file_size"])

            files = collect_files(codebase_root, extensions, skip_dirs, max_size)
            print(f"\n   Would index {len(files)} files")
            for f in files[:10]:
                print(f"   + {f.relative_to(codebase_root)}")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more")
        return

    # Use file locking for writes
    with FileLock(code_path):
        # Determine mode
        mode = 'open' if code_path.exists() else 'create'

        if code_path.exists() and not incremental:
            print(info("📝 Appending to existing code index..."))
            print("   (Use --fresh for clean reindex)")

        with memvid_sdk.use('basic', str(code_path), mode=mode) as mem:
            if incremental:
                indexed = index_files_incremental(mem, changed_files, config, args)
            else:
                indexed = index_files_full(mem, config, args)

    # Save state
    current_commit = get_current_commit()
    if current_commit:
        save_index_state(current_commit, indexed)

    print(f"\n{success('✅')} Indexed {indexed} files")
    print(f"   📦 Size: {format_size(code_path.stat().st_size)}")


def collect_files(root: Path, extensions: set, skip_dirs: set, max_size: int) -> list[Path]:
    """Collect all indexable files."""
    files = []
    for item in root.rglob('*'):
        if item.is_file():
            parts = item.relative_to(root).parts
            if any(p.startswith('.') or p in skip_dirs for p in parts):
                continue
            if item.suffix.lower() in extensions:
                if item.stat().st_size <= max_size:
                    files.append(item)
    return files


def index_files_full(mem, config: dict, args) -> int:
    """Full reindex of all files."""
    codebase_root = Path.cwd()
    extensions = get_extensions(config)
    skip_dirs = get_skip_dirs(config)
    max_size = parse_size(config["max_file_size"])
    verbose = config["output"]["verbose"] or getattr(args, 'verbose', False)

    print(f"📂 Scanning: {codebase_root}")
    files = collect_files(codebase_root, extensions, skip_dirs, max_size)
    print(f"   Found {len(files)} files")

    if not files:
        print(warning("   No indexable files found!"))
        return 0

    progress = ProgressBar(len(files), prefix="📂 Indexing: ")
    indexed = 0

    for filepath in files:
        try:
            relative_path = filepath.relative_to(codebase_root)
            content = filepath.read_text(encoding='utf-8', errors='ignore')

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
                    f"indexed_at:{datetime.now().isoformat()}"
                ]
            )
            indexed += 1

            if verbose:
                print(f"   + {relative_path}")

        except Exception as e:
            if verbose:
                print(warning(f"   ⚠️  Skip {filepath}: {e}"))

        progress.update()

    progress.finish()
    return indexed


def index_files_incremental(mem, changed_files: list[str], config: dict, args) -> int:
    """Incremental reindex of changed files only."""
    codebase_root = Path.cwd()
    extensions = get_extensions(config)
    max_size = parse_size(config["max_file_size"])
    verbose = config["output"]["verbose"] or getattr(args, 'verbose', False)

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
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            if not content.strip():
                continue

            mem.put(
                title=rel_path,
                text=content,
                uri=f"file://{rel_path}",
                tags=[
                    f"extension:{filepath.suffix}",
                    f"language:{detect_language(filepath.suffix)}",
                    f"indexed_at:{datetime.now().isoformat()}"
                ]
            )
            indexed += 1

            if verbose:
                print(f"   + {rel_path}")

        except Exception as e:
            if verbose:
                print(warning(f"   ⚠️  Skip {rel_path}: {e}"))

    return indexed


def cmd_remember(args):
    """Store a memory/decision/insight."""
    check_memvid()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print("❌ Twin-Mind not initialized. Run: twin-mind init")
        sys.exit(1)

    # Create title from message
    title = args.message[:50]
    if len(args.message) > 50:
        title += "..."

    # Build tags
    tags = [f"timestamp:{datetime.now().isoformat()}"]
    if args.tag:
        tags.append(f"category:{args.tag}")
    else:
        tags.append("category:general")

    with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
        mem.put(
            title=title,
            text=args.message,
            uri=f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags=tags
        )

    tag_str = f" [{args.tag}]" if args.tag else ""
    print(f"✅ Remembered{tag_str}: {title}")


def cmd_search(args):
    """Search code, memory, or both."""
    check_memvid()

    code_path = get_code_path()
    memory_path = get_memory_path()

    # Warn if code index is stale (when searching code)
    if args.scope in ('code', 'all') and code_path.exists():
        check_stale_index()

    # Check for --context and --full flags
    context_lines = getattr(args, 'context', None)
    show_full = getattr(args, 'full', False)

    # Adjust snippet size based on flags
    snippet_chars = 400
    if show_full:
        snippet_chars = 100000  # Get as much as possible
    elif context_lines:
        snippet_chars = max(400, context_lines * 200)

    results = []

    # Search code
    if args.scope in ('code', 'all') and code_path.exists():
        with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
            response = mem.find(args.query, k=args.top_k, snippet_chars=snippet_chars)
            for hit in response.get('hits', []):
                results.append(('code', hit))

    # Search memory
    if args.scope in ('memory', 'all') and memory_path.exists():
        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            response = mem.find(args.query, k=args.top_k, snippet_chars=snippet_chars)
            for hit in response.get('hits', []):
                results.append(('memory', hit))

    # Sort by score and limit
    results.sort(key=lambda x: x[1].get('score', 0), reverse=True)
    results = results[:args.top_k]

    if not results:
        print(f"🔍 No results for: '{args.query}'")
        return

    # JSON output with enhanced metadata
    if args.json:
        output = {
            "query": args.query,
            "results": [],
            "meta": {
                "scope": args.scope,
                "total_results": len(results)
            }
        }
        for source, hit in results:
            result_obj = {
                "source": source,
                "file": hit.get('title', ''),
                "score": hit.get('score', 0),
                "uri": hit.get('uri', ''),
                "snippet": hit.get('text', '').strip()
            }
            # Try to extract line numbers from URI for code
            uri = hit.get('uri', '')
            if source == 'code' and uri and uri.startswith('twin-mind://code/'):
                result_obj["file_path"] = uri.replace('twin-mind://code/', '')
            output["results"].append(result_obj)
        print(json.dumps(output, indent=2))
        return

    print(f"\n🔍 Results for: '{args.query}' (in: {args.scope})\n")
    print("=" * 60)

    for i, (source, hit) in enumerate(results, 1):
        icon = "📄" if source == 'code' else "📝"
        title = hit.get('title', 'untitled')

        print(f"\n{icon} [{i}] {title}")
        print(f"   Score: {hit.get('score', 0):.3f} | Source: {source}")
        print("-" * 40)

        # Get content to display
        content = hit.get('text', '').strip()

        # For code results with --full flag, try to read actual file
        uri = hit.get('uri', '')
        if source == 'code' and show_full and uri:
            file_path = uri.replace('file://', '')
            if Path(file_path).exists():
                try:
                    content = Path(file_path).read_text()
                    print(f"   [Full file: {file_path}]")
                except Exception:
                    pass  # Fall back to stored snippet

        # For code results with --context, show more lines
        if source == 'code' and context_lines and not show_full:
            # The snippet already has more chars, just show more lines
            lines = content.split('\n')
            max_lines = min(len(lines), context_lines * 2 + 10)
            content = '\n'.join(lines[:max_lines])

        # Display content
        if show_full:
            # Show full content with line numbers
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                print(f"   {line_num:4d} | {line}")
        else:
            # Show limited snippet
            max_chars = 300 if not context_lines else context_lines * 100
            max_lines = 8 if not context_lines else context_lines * 2
            snippet = content[:max_chars]
            indented = "\n".join(f"   {line}" for line in snippet.split("\n")[:max_lines])
            print(indented)


def cmd_ask(args):
    """Ask a question (searches both stores)."""
    args.scope = 'all'
    args.top_k = 5
    args.json = False
    args.query = args.question
    cmd_search(args)


def cmd_recent(args):
    """Show recent memories."""
    check_memvid()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print("❌ No memory store. Run: twin-mind init")
        sys.exit(1)

    with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
        entries = mem.timeline()
        # Sort by timestamp descending (most recent first) and limit
        entries = sorted(entries, key=lambda x: x.get('timestamp', 0), reverse=True)[:args.n]

    if not entries:
        print("📭 No memories yet. Use: twin-mind remember <message>")
        return

    print(f"\n📝 Recent Memories ({len(entries)})\n")
    print("=" * 60)

    for i, entry in enumerate(entries, 1):
        # Extract title from preview (format: "text\ntitle: X\nuri: Y\ntags: Z")
        preview = entry.get('preview', '')
        title = 'untitled'
        text = preview
        if '\ntitle: ' in preview:
            parts = preview.split('\ntitle: ')
            text = parts[0]
            title_part = parts[1].split('\n')[0] if len(parts) > 1 else ''
            title = title_part or 'untitled'
        print(f"\n[{i}] {title}")
        print(f"    {text[:150]}")


def cmd_stats(args):
    """Show twin-mind statistics."""
    check_memvid()

    code_path = get_code_path()
    memory_path = get_memory_path()

    print(f"\n🧠 Twin-Mind Stats")
    print("=" * 45)

    # Code stats
    if code_path.exists():
        code_size = format_size(code_path.stat().st_size)
        with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
            stats = mem.stats()
            frame_count = stats.get('frame_count', 0)

        # Get actual file count from index state
        index_state = load_index_state()
        file_count = index_state.get('file_count', '?') if index_state else '?'

        print(f"📄 Code Store:   {code_path}")
        print(f"   Size:         {code_size}")
        print(f"   Files:        {file_count}")
        print(f"   Frames:       {frame_count}")
    else:
        print(f"📄 Code Store:   Not created")

    print()

    # Memory stats
    if memory_path.exists():
        mem_size = format_size(memory_path.stat().st_size)
        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            stats = mem.stats()
            mem_count = stats.get('frame_count', 0)
        print(f"📝 Memory Store: {memory_path}")
        print(f"   Size:         {mem_size}")
        print(f"   Memories:     {mem_count}")
    else:
        print(f"📝 Memory Store: Not created")

    print("=" * 45)


def cmd_reset(args):
    """Reset code, memory, or both stores."""
    check_memvid()

    dry_run = getattr(args, 'dry_run', False)
    code_path = get_code_path()
    memory_path = get_memory_path()

    target = args.target

    if dry_run:
        print(info("🔍 Reset preview (dry-run):"))

    if target in ('code', 'all'):
        if code_path.exists():
            size = format_size(code_path.stat().st_size)
            if dry_run:
                print(f"   Would reset code store ({size})")
            elif args.force or confirm(f"⚠️  Delete code store ({size})?"):
                code_path.unlink()
                with memvid_sdk.use('basic', str(code_path), mode='create') as mem:
                    pass  # Just create empty store
                print(success("✅ Code store reset"))
            else:
                print("   Skipped code store")
        else:
            print("   Code store doesn't exist")

    if target in ('memory', 'all'):
        if memory_path.exists():
            size = format_size(memory_path.stat().st_size)
            if dry_run:
                print(f"   Would reset memory store ({size})")
            elif args.force or confirm(f"⚠️  Delete memory store ({size})? This is PERMANENT!"):
                memory_path.unlink()
                with memvid_sdk.use('basic', str(memory_path), mode='create') as mem:
                    mem.put(
                        title="Memory Reset",
                        text=f"Memory reset on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        uri="twin-mind://system/reset",
                        tags=["category:system", f"timestamp:{datetime.now().isoformat()}"]
                    )
                print(success("✅ Memory store reset"))
            else:
                print("   Skipped memory store")
        else:
            print("   Memory store doesn't exist")


def cmd_prune(args):
    """Prune old memories via filtered rebuild."""
    check_memvid()

    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print(error("❌ No memory store. Run: twin-mind init"))
        sys.exit(1)

    # Parse date filter
    cutoff = None
    if args.before:
        if re.match(r'^\d+d$', args.before):
            days = int(args.before[:-1])
            cutoff = datetime.now() - timedelta(days=days)
        elif re.match(r'^\d+w$', args.before):
            weeks = int(args.before[:-1])
            cutoff = datetime.now() - timedelta(weeks=weeks)
        else:
            try:
                cutoff = datetime.fromisoformat(args.before)
            except ValueError:
                print(error(f"❌ Invalid date format: {args.before}"))
                print("   Use: YYYY-MM-DD, 30d (days), or 2w (weeks)")
                sys.exit(1)

    if not cutoff and not args.tag:
        print(error("❌ Specify --before DATE or --tag TAG to prune"))
        sys.exit(1)

    # Load all memories using timeline
    with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
        all_entries = mem.timeline()

    if not all_entries:
        print("📭 No memories to prune")
        return

    # Filter memories to remove
    to_remove = []
    to_keep = []

    for entry in all_entries:
        should_remove = False
        uri = entry.get('uri', '')
        preview = entry.get('preview', '')

        # Skip system entries - always keep
        if uri and "twin-mind://system" in uri:
            to_keep.append(entry)
            continue

        # Check date filter
        if cutoff and uri:
            try:
                # URI format: twin-mind://memory/YYYYMMDD_HHMMSS
                if "twin-mind://memory/" in uri:
                    date_part = uri.split("/")[-1]
                    mem_date = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                    if mem_date < cutoff:
                        should_remove = True
            except (ValueError, IndexError):
                pass

        # Check tag filter
        if args.tag:
            tag_lower = args.tag.lower()
            # Extract title from preview
            title = ''
            if '\ntitle: ' in preview:
                title = preview.split('\ntitle: ')[1].split('\n')[0]
            if tag_lower in title.lower() or f"[{tag_lower}]" in preview.lower():
                should_remove = True

        if should_remove:
            to_remove.append(entry)
        else:
            to_keep.append(entry)

    if not to_remove:
        print(success("✅ No memories match prune criteria"))
        return

    # Show preview
    print(f"\n🔍 Prune preview:")
    print(f"   Matching: {len(to_remove)} memories")
    for entry in to_remove[:5]:
        parsed = parse_timeline_entry(entry)
        title = parsed['title'][:50]
        print(f"   - \"{title}\"")
    if len(to_remove) > 5:
        print(f"   ... and {len(to_remove) - 5} more")

    # Dry run stops here
    if getattr(args, 'dry_run', False):
        print(f"\n   Would keep {len(to_keep)} memories")
        return

    # Confirm
    if not getattr(args, 'force', False):
        if not confirm(f"\n⚠️  Delete {len(to_remove)} memories?"):
            print("   Cancelled")
            return

    # Backup
    import shutil
    backup_path = Path(str(memory_path) + '.backup')
    shutil.copy2(memory_path, backup_path)
    print(f"💾 Backed up to {backup_path}")

    # Rebuild with kept memories
    memory_path.unlink()
    with memvid_sdk.use('basic', str(memory_path), mode='create') as new_mem:
        for entry in to_keep:
            parsed = parse_timeline_entry(entry)
            new_mem.put(
                title=parsed['title'],
                text=parsed['text'],
                uri=parsed['uri'] or f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                tags=parsed['tags']
            )

    print(success(f"✅ Pruned {len(to_remove)} memories ({len(to_keep)} remaining)"))


def cmd_context(args):
    """Generate combined code+memory context for prompts."""
    check_memvid()

    code_path = get_code_path()
    memory_path = get_memory_path()

    query = args.query
    max_tokens = getattr(args, 'max_tokens', 4000)

    # Collect results
    code_results = []
    memory_results = []

    # Search code
    if code_path.exists():
        with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
            response = mem.find(query, k=5, snippet_chars=2000)
            code_results = response.get('hits', [])[:3]  # Top 3 code results

    # Search memory
    if memory_path.exists():
        with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
            response = mem.find(query, k=5, snippet_chars=1000)
            memory_results = response.get('hits', [])[:3]  # Top 3 memory results

    # Build context document
    context_parts = []
    total_chars = 0
    char_limit = max_tokens * 4  # Rough char-to-token ratio

    # Add relevant code first
    if code_results:
        context_parts.append("## Relevant Code\n")
        for hit in code_results:
            if total_chars >= char_limit:
                break
            file_name = hit.get('title', 'file')
            text = hit.get('text', '').strip()[:1500]
            code_block = f"### {file_name}\n```\n{text}\n```\n"
            context_parts.append(code_block)
            total_chars += len(code_block)

    # Add relevant memories
    if memory_results:
        context_parts.append("\n## Relevant Memories\n")
        for hit in memory_results:
            if total_chars >= char_limit:
                break
            title = hit.get('title', 'Memory')
            text = hit.get('text', '').strip()[:500]
            memory_block = f"- **{title}**: {text}\n"
            context_parts.append(memory_block)
            total_chars += len(memory_block)

    # Output
    if not context_parts:
        print(f"No relevant context found for: {query}")
        return

    context = "\n".join(context_parts)

    if getattr(args, 'json', False):
        output = {
            "query": query,
            "context": context,
            "code_results": len(code_results),
            "memory_results": len(memory_results),
            "total_chars": len(context)
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"# Context for: {query}\n")
        print(context)
        print(f"\n---\n_Generated from {len(code_results)} code files and {len(memory_results)} memories_")


def cmd_export(args):
    """Export memories to readable format."""
    check_memvid()

    memory_path = get_memory_path()

    if not memory_path.exists():
        print("❌ No memory store. Run: twin-mind init")
        sys.exit(1)

    # Get all memories using timeline, then fetch full frame data
    memories = []
    with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
        entries = mem.timeline()
        for entry in entries:
            # Parse text from preview (before metadata lines)
            parsed = parse_timeline_entry(entry)

            # Get full metadata from frame() for accurate title/tags
            uri = entry.get('uri', '')
            if uri:
                try:
                    frame = mem.frame(uri)
                    parsed['title'] = frame.get('title', parsed['title'])
                    parsed['tags'] = frame.get('tags', parsed['tags'])
                    parsed['uri'] = frame.get('uri', parsed['uri'])
                except Exception:
                    pass  # Use parsed values if frame lookup fails

            memories.append(parsed)

    if not memories:
        print("📭 No memories to export")
        return

    if args.format == 'json':
        output = []
        for mem_data in memories:
            output.append({
                "title": mem_data['title'],
                "content": mem_data['text'],
                "uri": mem_data['uri'],
                "tags": mem_data['tags']
            })
        result = json.dumps(output, indent=2, ensure_ascii=False)
    else:  # markdown
        lines = ["# Twin-Mind Memory Export", ""]
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total memories: {len(memories)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, mem_data in enumerate(memories, 1):
            title = mem_data['title']
            text = mem_data['text'].strip()
            uri = mem_data['uri']
            tags = mem_data['tags']
            lines.append(f"## {i}. {title}")
            lines.append("")
            lines.append(text)
            lines.append("")
            if tags:
                lines.append(f"*Tags: {', '.join(tags)}*")
            if uri:
                lines.append(f"*URI: {uri}*")
            lines.append("")
            lines.append("---")
            lines.append("")

        result = "\n".join(lines)

    # Output to file or stdout
    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"✅ Exported {len(memories)} memories to {args.output}")
    else:
        print(result)


def cmd_status(args):
    """Show twin-mind health status."""
    check_memvid()

    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    code_path = get_code_path()
    memory_path = get_memory_path()

    print(f"\n🧠 Twin-Mind Status")
    print("═" * 50)

    # Code stats
    if code_path.exists():
        code_size = format_size(code_path.stat().st_size)
        try:
            with memvid_sdk.use('basic', str(code_path), mode='open') as mem:
                stats = mem.stats()
                frame_count = stats.get('frame_count', 0)
        except Exception:
            frame_count = "?"

        # Get actual file count from index state
        index_state = load_index_state()
        file_count = index_state.get('file_count', '?') if index_state else '?'

        age = get_index_age() or "unknown"
        print(f"📄 Code     {code_size:>8} │ {file_count} files, {frame_count} frames │ indexed {age}")
    else:
        print(f"📄 Code     {warning('not created')}")

    # Memory stats
    if memory_path.exists():
        mem_size = format_size(memory_path.stat().st_size)
        try:
            with memvid_sdk.use('basic', str(memory_path), mode='open') as mem:
                stats = mem.stats()
                mem_count = stats.get('frame_count', 0)
        except Exception:
            mem_count = "?"
        print(f"📝 Memory   {mem_size:>8} │ {mem_count} entries")
    else:
        print(f"📝 Memory   {warning('not created')}")

    # Git status
    if is_git_repo():
        branch = get_branch_name()
        commit = get_current_commit()
        commit_short = commit[:7] if commit else "?"

        state = load_index_state()
        if state and commit:
            behind = get_commits_behind(state.get("last_commit", commit))
            if behind > 0:
                git_status = warning(f"{behind} commits ahead of index")
            elif behind == 0:
                git_status = success("up to date")
            else:
                git_status = "unknown"
        else:
            git_status = "not indexed yet"

        print(f"🔗 Git      {branch} @ {commit_short} ({git_status})")

    print("═" * 50)


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


# === Main ===

def main():
    parser = argparse.ArgumentParser(
        prog='twin-mind',
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

Repository: https://github.com/your-username/twin-mind
"""
    )

    parser.add_argument('--version', '-V', action='version', version=f'twin-mind {VERSION}')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init
    p_init = subparsers.add_parser('init', help='Initialize twin-mind')
    p_init.add_argument('--banner', '-b', action='store_true', help='Show ASCII banner')

    # index
    p_index = subparsers.add_parser('index', help='Index codebase')
    p_index.add_argument('--fresh', '-f', action='store_true',
                         help='Delete existing index and rebuild from scratch')
    p_index.add_argument('--status', '-s', action='store_true',
                         help='Preview what would be indexed without executing')
    p_index.add_argument('--dry-run', action='store_true',
                         help='Same as --status')
    p_index.add_argument('--verbose', '-v', action='store_true',
                         help='Show each file as it is processed')

    # remember
    p_remember = subparsers.add_parser('remember', help='Store a memory')
    p_remember.add_argument('message', help='What to remember')
    p_remember.add_argument('--tag', '-t', help='Category tag (arch, bugfix, feature, etc.)')

    # search
    p_search = subparsers.add_parser('search', help='Search twin-mind')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('--in', dest='scope', choices=['code', 'memory', 'all'],
                          default='all', help='Where to search (default: all)')
    p_search.add_argument('--top-k', '-k', type=int, default=10, help='Number of results')
    p_search.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    p_search.add_argument('--context', '-c', type=int, metavar='N',
                          help='Show N lines before/after each match')
    p_search.add_argument('--full', action='store_true',
                          help='Show full file content for code matches')

    # ask
    p_ask = subparsers.add_parser('ask', help='Ask a question')
    p_ask.add_argument('question', help='Your question')

    # recent
    p_recent = subparsers.add_parser('recent', help='Show recent memories')
    p_recent.add_argument('--n', type=int, default=10, help='Number to show')

    # stats
    subparsers.add_parser('stats', help='Show twin-mind statistics')

    # status
    subparsers.add_parser('status', help='Show twin-mind health status')

    # reindex
    p_reindex = subparsers.add_parser('reindex', help='Reset code and reindex fresh')
    p_reindex.add_argument('--verbose', '-v', action='store_true', help='Show each file')

    # reset
    p_reset = subparsers.add_parser('reset', help='Reset a memory store')
    p_reset.add_argument('target', choices=['code', 'memory', 'all'], help='What to reset')
    p_reset.add_argument('--force', '-f', action='store_true', help='Skip confirmation')
    p_reset.add_argument('--dry-run', action='store_true', help='Preview without executing')

    # prune
    p_prune = subparsers.add_parser('prune', help='Prune old memories')
    p_prune.add_argument('target', choices=['memory'], help='What to prune')
    p_prune.add_argument('--before', '-b', help='Remove before date (YYYY-MM-DD, 30d, 2w)')
    p_prune.add_argument('--tag', '-t', help='Remove by tag')
    p_prune.add_argument('--dry-run', action='store_true', help='Preview without executing')
    p_prune.add_argument('--force', action='store_true', help='Skip confirmation')

    # context
    p_context = subparsers.add_parser('context', help='Generate combined context for prompts')
    p_context.add_argument('query', help='Query to build context for')
    p_context.add_argument('--max-tokens', '-m', type=int, default=4000,
                           help='Maximum tokens for context (default: 4000)')
    p_context.add_argument('--json', '-j', action='store_true', help='Output as JSON')

    # export
    p_export = subparsers.add_parser('export', help='Export memories')
    p_export.add_argument('--format', '-f', choices=['md', 'json'], default='md', help='Output format')
    p_export.add_argument('--output', '-o', help='Output file (default: stdout)')

    args = parser.parse_args()

    # Handle --no-color flag globally
    if args.no_color:
        Colors.disable()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        'init': cmd_init,
        'index': cmd_index,
        'remember': cmd_remember,
        'search': cmd_search,
        'ask': cmd_ask,
        'recent': cmd_recent,
        'stats': cmd_stats,
        'status': cmd_status,
        'reindex': cmd_reindex,
        'reset': cmd_reset,
        'prune': cmd_prune,
        'context': cmd_context,
        'export': cmd_export
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
