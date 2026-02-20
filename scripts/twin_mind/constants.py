"""Constants for twin-mind."""

VERSION = "1.10.0"

# Directory and file names
BRAIN_DIR = ".claude"
CODE_FILE = "code.mv2"
MEMORY_FILE = "memory.mv2"
DECISIONS_MV2_FILE = "decisions.mv2"
ENTITIES_DB_FILE = "entities.sqlite"
INDEX_STATE_FILE = "index-state.json"
GITIGNORE_FILE = ".gitignore"

GITIGNORE_CONTENT = """# Twin-Mind gitignore
#
# code.mv2 - Generated codebase index (regeneratable)
# index-state.json - Machine-specific index metadata
# memory.mv2 - Local/personal memories (not shared)
# decisions.mv2 - Semantic index (regeneratable from decisions.jsonl)
# entities.sqlite - Entity graph index (regeneratable from code)
#
# decisions.jsonl IS versioned - shared team decisions (JSONL = mergeable)

code.mv2
index-state.json
memory.mv2
decisions.mv2
entities.sqlite
"""

# Default extensions to index
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".sql",
    ".sh",
    ".bash",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".txt",
    ".vue",
    ".svelte",
    ".astro",
    ".prisma",
    ".graphql",
    ".proto",
    ".tf",
}

# Directories to skip during indexing
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    "vendor",
    ".claude",
    ".terraform",
    ".serverless",
    "cdk.out",
    ".aws-sam",
}

MAX_FILE_SIZE = 500 * 1024  # 500KB

# Directories where auto-init should be skipped
UNSAFE_DIRS = {
    "/",
    "/usr",
    "/etc",
    "/var",
    "/tmp",
    "/opt",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/Applications",  # macOS
    "/Windows",
    "/Program Files",
    "/Program Files (x86)",  # Windows
}

# Default configuration
DEFAULT_CONFIG = {
    "extensions": {"include": [], "exclude": []},
    "skip_dirs": [],
    "max_file_size": "500KB",
    "index": {
        "auto_incremental": True,
        "track_deletions": True,
        "parallel": True,  # Enable parallel ingestion (3-6x faster)
        "parallel_workers": 4,  # Number of parallel workers
        "embedding_model": None,  # None=default, "bge-small", "bge-base", "gte-large", "openai"
        "adaptive_retrieval": True,  # Auto-determine optimal result count
    },
    "output": {"color": True, "verbose": False},
    "memory": {
        "share_memories": False,  # If True, memories go to shared decisions.jsonl
        "dedupe": True,  # Enable SimHash deduplication
    },
    "decisions": {
        "build_semantic_index": True,
    },
    "entities": {
        "enabled": True,
    },
    "maintenance": {
        "size_warnings": True,
        "code_max_mb": 50,
        "memory_max_mb": 15,
        "decisions_max_mb": 5,
    },
}
