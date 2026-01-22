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
    from memvid_sdk import Memvid, PutOptions, SearchRequest
    MEMVID_AVAILABLE = True
except ImportError:
    MEMVID_AVAILABLE = False


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
VERSION = "1.0.0"

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
    multipliers = {'B': 1, 'KB': 1024, 'MB': 1024*1024, 'GB': 1024**3}
    for suffix, mult in multipliers.items():
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


# === Helpers ===

def check_memvid():
    if not MEMVID_AVAILABLE:
        print("❌ memvid-sdk not installed.")
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
    print("""
  ______         _          __  __ _           _ 
 |__  __|       (_)        |  \/  (_)         | |
    | |_      __ _ _ __    | \  / |_ _ __   __| |
    | \ \ /\ / / | '_ \   | |\/| | | '_ \ / _` |
    | |\ V  V /| | | | |  | |  | | | | | | (_| |
    |_| \_/\_/ |_|_| |_|  |_|  |_|_|_| |_|\__,_|
    
    Dual Memory for AI Coding Agents v{version}
    """.format(version=VERSION))


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
    code_mem = Memvid.create(str(code_path))
    code_mem.commit()
    
    # Initialize memory store with welcome message
    if memory_path.exists():
        memory_path.unlink()
    memory_mem = Memvid.create(str(memory_path))
    
    opts = PutOptions.builder() \
        .title("Twin-Mind Initialized") \
        .uri("twin-mind://system/init") \
        .tag("category", "system") \
        .tag("timestamp", datetime.now().isoformat()) \
        .build()
    
    init_msg = f"Twin-Mind initialized on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    memory_mem.put_bytes_with_options(init_msg.encode('utf-8'), opts)
    memory_mem.commit()
    
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
    
    code_path = get_code_path()
    
    if not get_brain_dir().exists():
        print("❌ Twin-Mind not initialized. Run: twin-mind init")
        sys.exit(1)
    
    # Fresh index = delete and recreate
    if args.fresh and code_path.exists():
        print("🔄 Fresh index requested, resetting code store...")
        code_path.unlink()
    
    # Create or open
    if code_path.exists():
        print("📝 Appending to existing code index...")
        print("   (Use --fresh for clean reindex)")
        mem = Memvid.open(str(code_path))
    else:
        mem = Memvid.create(str(code_path))
    
    # Collect files
    codebase_root = Path.cwd()
    print(f"📂 Scanning: {codebase_root}")
    
    files = []
    for item in codebase_root.rglob('*'):
        if item.is_file():
            parts = item.relative_to(codebase_root).parts
            if any(p.startswith('.') or p in SKIP_DIRS for p in parts):
                continue
            if item.suffix.lower() in CODE_EXTENSIONS:
                if item.stat().st_size <= MAX_FILE_SIZE:
                    files.append(item)
    
    print(f"   Found {len(files)} files")
    
    if not files:
        print("   No indexable files found!")
        return
    
    # Index files
    indexed = 0
    for filepath in files:
        try:
            relative_path = filepath.relative_to(codebase_root)
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            
            if not content.strip():
                continue
            
            opts = PutOptions.builder() \
                .title(str(relative_path)) \
                .uri(f"file://{relative_path}") \
                .tag("extension", filepath.suffix) \
                .tag("language", detect_language(filepath.suffix)) \
                .tag("indexed_at", datetime.now().isoformat()) \
                .build()
            
            mem.put_bytes_with_options(content.encode('utf-8'), opts)
            indexed += 1
            
            if indexed % 50 == 0:
                print(f"   Indexed {indexed}...")
                
        except Exception:
            pass
    
    mem.commit()
    
    print(f"""
✅ Indexed {indexed} files
   📦 Size: {format_size(code_path.stat().st_size)}
""")


def cmd_remember(args):
    """Store a memory/decision/insight."""
    check_memvid()
    
    memory_path = get_memory_path()
    
    if not memory_path.exists():
        print("❌ Twin-Mind not initialized. Run: twin-mind init")
        sys.exit(1)
    
    mem = Memvid.open(str(memory_path))
    
    # Create title from message
    title = args.message[:50]
    if len(args.message) > 50:
        title += "..."
    
    # Build options
    builder = PutOptions.builder() \
        .title(title) \
        .uri(f"twin-mind://memory/{datetime.now().strftime('%Y%m%d_%H%M%S')}") \
        .tag("timestamp", datetime.now().isoformat())
    
    if args.tag:
        builder.tag("category", args.tag)
    else:
        builder.tag("category", "general")
    
    opts = builder.build()
    mem.put_bytes_with_options(args.message.encode('utf-8'), opts)
    mem.commit()
    
    tag_str = f" [{args.tag}]" if args.tag else ""
    print(f"✅ Remembered{tag_str}: {title}")


def cmd_search(args):
    """Search code, memory, or both."""
    check_memvid()
    
    code_path = get_code_path()
    memory_path = get_memory_path()
    
    results = []
    
    # Search code
    if args.scope in ('code', 'all') and code_path.exists():
        mem = Memvid.open(str(code_path))
        req = SearchRequest(
            query=args.query,
            top_k=args.top_k,
            snippet_chars=400
        )
        response = mem.search(req)
        for hit in response.hits:
            results.append(('code', hit))
    
    # Search memory
    if args.scope in ('memory', 'all') and memory_path.exists():
        mem = Memvid.open(str(memory_path))
        req = SearchRequest(
            query=args.query,
            top_k=args.top_k,
            snippet_chars=400
        )
        response = mem.search(req)
        for hit in response.hits:
            results.append(('memory', hit))
    
    # Sort by score and limit
    results.sort(key=lambda x: x[1].score, reverse=True)
    results = results[:args.top_k]
    
    if not results:
        print(f"🔍 No results for: '{args.query}'")
        return
    
    # JSON output
    if args.json:
        output = []
        for source, hit in results:
            output.append({
                "source": source,
                "title": hit.title,
                "score": hit.score,
                "uri": hit.uri,
                "snippet": hit.text.strip()[:300]
            })
        print(json.dumps(output, indent=2))
        return
    
    print(f"\n🔍 Results for: '{args.query}' (in: {args.scope})\n")
    print("=" * 60)
    
    for i, (source, hit) in enumerate(results, 1):
        icon = "📄" if source == 'code' else "📝"
        title = hit.title or "untitled"
        
        print(f"\n{icon} [{i}] {title}")
        print(f"   Score: {hit.score:.3f} | Source: {source}")
        print("-" * 40)
        
        snippet = hit.text.strip()[:300]
        indented = "\n".join(f"   {line}" for line in snippet.split("\n")[:8])
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
    
    mem = Memvid.open(str(memory_path))
    
    req = SearchRequest(
        query="*",
        top_k=args.n,
        snippet_chars=200
    )
    response = mem.search(req)
    
    if not response.hits:
        print("📭 No memories yet. Use: twin-mind remember <message>")
        return
    
    print(f"\n📝 Recent Memories ({len(response.hits)})\n")
    print("=" * 60)
    
    for i, hit in enumerate(response.hits, 1):
        title = hit.title or "untitled"
        print(f"\n[{i}] {title}")
        print(f"    {hit.text.strip()[:150]}")


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
        mem = Memvid.open(str(code_path))
        code_count = len(mem.search(SearchRequest(query="*", top_k=10000)).hits)
        print(f"📄 Code Store:   {code_path}")
        print(f"   Size:         {code_size}")
        print(f"   Files:        {code_count}")
    else:
        print(f"📄 Code Store:   Not created")
    
    print()
    
    # Memory stats
    if memory_path.exists():
        mem_size = format_size(memory_path.stat().st_size)
        mem = Memvid.open(str(memory_path))
        mem_count = len(mem.search(SearchRequest(query="*", top_k=10000)).hits)
        print(f"📝 Memory Store: {memory_path}")
        print(f"   Size:         {mem_size}")
        print(f"   Memories:     {mem_count}")
    else:
        print(f"📝 Memory Store: Not created")
    
    print("=" * 45)


def cmd_reset(args):
    """Reset code, memory, or both stores."""
    check_memvid()
    
    code_path = get_code_path()
    memory_path = get_memory_path()
    
    target = args.target
    
    if target in ('code', 'all'):
        if code_path.exists():
            if args.force or confirm(f"⚠️  Delete code store ({format_size(code_path.stat().st_size)})?"):
                code_path.unlink()
                mem = Memvid.create(str(code_path))
                mem.commit()
                print(f"✅ Code store reset")
            else:
                print("   Skipped code store")
        else:
            print("   Code store doesn't exist")
    
    if target in ('memory', 'all'):
        if memory_path.exists():
            if args.force or confirm(f"⚠️  Delete memory store ({format_size(memory_path.stat().st_size)})? This is PERMANENT!"):
                memory_path.unlink()
                mem = Memvid.create(str(memory_path))
                opts = PutOptions.builder() \
                    .title("Memory Reset") \
                    .uri("twin-mind://system/reset") \
                    .tag("category", "system") \
                    .tag("timestamp", datetime.now().isoformat()) \
                    .build()
                mem.put_bytes_with_options(
                    f"Memory reset on {datetime.now().strftime('%Y-%m-%d %H:%M')}".encode('utf-8'),
                    opts
                )
                mem.commit()
                print(f"✅ Memory store reset")
            else:
                print("   Skipped memory store")
        else:
            print("   Memory store doesn't exist")


def cmd_prune(args):
    """Prune old memories."""
    check_memvid()
    
    memory_path = get_memory_path()
    
    if not memory_path.exists():
        print("❌ No memory store. Run: twin-mind init")
        sys.exit(1)
    
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
                print(f"❌ Invalid date format: {args.before}")
                print("   Use: YYYY-MM-DD, 30d (days), or 2w (weeks)")
                sys.exit(1)
    
    if not cutoff and not args.tag:
        print("❌ Specify --before DATE or --tag TAG to prune")
        sys.exit(1)
    
    print(f"⚠️  Pruning is not yet implemented in memvid-sdk")
    print(f"   Workaround: Use 'twin-mind reset memory' to clear all")
    print(f"   Then manually re-add important memories")


def cmd_export(args):
    """Export memories to readable format."""
    check_memvid()
    
    memory_path = get_memory_path()
    
    if not memory_path.exists():
        print("❌ No memory store. Run: twin-mind init")
        sys.exit(1)
    
    mem = Memvid.open(str(memory_path))
    
    req = SearchRequest(query="*", top_k=10000, snippet_chars=5000)
    response = mem.search(req)
    
    if not response.hits:
        print("📭 No memories to export")
        return
    
    if args.format == 'json':
        output = []
        for hit in response.hits:
            output.append({
                "title": hit.title,
                "content": hit.text,
                "uri": hit.uri,
                "score": hit.score
            })
        result = json.dumps(output, indent=2, ensure_ascii=False)
    else:  # markdown
        lines = ["# Twin-Mind Memory Export", ""]
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total memories: {len(response.hits)}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for i, hit in enumerate(response.hits, 1):
            lines.append(f"## {i}. {hit.title or 'Untitled'}")
            lines.append("")
            lines.append(hit.text.strip())
            lines.append("")
            if hit.uri:
                lines.append(f"*URI: {hit.uri}*")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        result = "\n".join(lines)
    
    # Output to file or stdout
    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"✅ Exported {len(response.hits)} memories to {args.output}")
    else:
        print(result)


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
    
    parser.add_argument('--version', '-v', action='version', version=f'twin-mind {VERSION}')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # init
    p_init = subparsers.add_parser('init', help='Initialize twin-mind')
    p_init.add_argument('--banner', '-b', action='store_true', help='Show ASCII banner')
    
    # index
    p_index = subparsers.add_parser('index', help='Index codebase')
    p_index.add_argument('--fresh', '-f', action='store_true',
                         help='Delete existing index and rebuild from scratch')
    
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
    
    # ask
    p_ask = subparsers.add_parser('ask', help='Ask a question')
    p_ask.add_argument('question', help='Your question')
    
    # recent
    p_recent = subparsers.add_parser('recent', help='Show recent memories')
    p_recent.add_argument('--n', type=int, default=10, help='Number to show')
    
    # stats
    subparsers.add_parser('stats', help='Show twin-mind statistics')
    
    # reset
    p_reset = subparsers.add_parser('reset', help='Reset a memory store')
    p_reset.add_argument('target', choices=['code', 'memory', 'all'], help='What to reset')
    p_reset.add_argument('--force', '-f', action='store_true', help='Skip confirmation')
    
    # prune
    p_prune = subparsers.add_parser('prune', help='Prune old memories')
    p_prune.add_argument('target', choices=['memory'], help='What to prune')
    p_prune.add_argument('--before', '-b', help='Remove before date (YYYY-MM-DD, 30d, 2w)')
    p_prune.add_argument('--tag', '-t', help='Remove by tag')
    
    # export
    p_export = subparsers.add_parser('export', help='Export memories')
    p_export.add_argument('--format', '-f', choices=['md', 'json'], default='md', help='Output format')
    p_export.add_argument('--output', '-o', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
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
        'reset': cmd_reset,
        'prune': cmd_prune,
        'export': cmd_export
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
