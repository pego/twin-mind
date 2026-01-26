# Twin-Mind

**Dual memory for AI coding agents** - Codebase knowledge + Conversation memory with team-friendly sharing.

[![CI](https://github.com/pego/twin-mind/actions/workflows/ci.yml/badge.svg)](https://github.com/pego/twin-mind/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pego/twin-mind/graph/badge.svg)](https://codecov.io/gh/pego/twin-mind)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Memvid](https://img.shields.io/badge/powered%20by-memvid-orange.svg)](https://github.com/memvid/memvid)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

---

## The Problem

```
You: "Remember that auth bug we fixed?"
Claude: "I don't have memory of previous conversations."

You: "Where's the payment processing code?"
Claude: "I'd need to search through your files..."
```

**200K context window. Zero memory between sessions. No codebase understanding.**

## The Solution

```
You: "What did we decide about auth?"
Claude: "We chose JWT over sessions. Here's the middleware...
        And here's why we made that decision last week."
```

Claude remembers everything - code AND decisions. Team decisions are shared and mergeable.

---

## Quick Start

### One-Command Install

```bash
curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash
```

Then restart your terminal (or run `source ~/.zshrc`).

### First Use

```bash
cd ~/your-project
twin-mind search "authentication"
```

That's it! First command auto-initializes the project.

---

## Architecture

```
your-project/.claude/
├── code.mv2           # Codebase index (gitignored)
├── memory.mv2         # Local memories (gitignored)
├── decisions.jsonl    # Shared decisions (versioned, mergeable)
└── index-state.json   # Index metadata (gitignored)
```

### Memory Types

| Type | File | Versioned | Use Case |
|------|------|-----------|----------|
| **Code** | `code.mv2` | No | Indexed source code |
| **Local** | `memory.mv2` | No | Personal notes, session context |
| **Shared** | `decisions.jsonl` | **Yes** | Team decisions, architecture choices |

**Why this structure?**
- `decisions.jsonl` uses JSONL format = git can merge parallel additions
- Local memories stay private, shared decisions become team knowledge
- Code index is regeneratable, no need to version

---

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `search <query>` | Search code + all memories |
| `search <query> --in code` | Search only code |
| `search <query> --in memory` | Search only memories (local + shared) |
| `remember <msg>` | Store locally (default) |
| `remember <msg> --share` | Store to shared decisions |
| `remember <msg> --local` | Force store locally |
| `context <query>` | Combined code+memory for prompts |
| `status` | Health check |
| `stats` | Display statistics |
| `recent` | Show recent memories (local + shared) |

### Index Commands

| Command | Description |
|---------|-------------|
| `index` | Incremental index (git-based, fast) |
| `index --fresh` | Full rebuild from scratch |
| `index --status` | Preview what would be indexed |
| `reindex` | Reset code + fresh index |

### Management Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize memory stores |
| `reset code` | Clear code index |
| `reset memory` | Clear local memories |
| `prune memory --before 30d` | Remove old memories |
| `export --format md` | Export memories to markdown |
| `doctor` | Health check and diagnostics |
| `doctor --vacuum` | Reclaim space from deletions |
| `upgrade` | Check for updates and upgrade |
| `upgrade --check` | Only check, don't install |
| `uninstall` | Remove twin-mind installation |

---

## Team Sharing

Twin-Mind's hybrid memory system separates personal notes from team knowledge, enabling seamless collaboration without merge conflicts.

### Local vs Shared Memory

| Aspect | Local (`memory.mv2`) | Shared (`decisions.jsonl`) |
|--------|---------------------|---------------------------|
| **Purpose** | Personal notes, TODOs, session context | Team decisions, architecture choices |
| **Git** | Ignored (`.gitignore`) | Versioned and committed |
| **Visibility** | Only you | Entire team |
| **Format** | Binary (memvid) | JSONL (text, mergeable) |
| **Persistence** | Machine-local | Across all clones |

### Saving Memories

```bash
# Default: save locally (personal)
twin-mind remember "Need to refactor this tomorrow" --tag todo

# Explicit share: save to team decisions
twin-mind remember "Chose JWT over sessions for stateless auth" --tag arch --share

# Force local even when share_memories is enabled
twin-mind remember "My debugging notes" --tag debug --local
```

### Team Configuration

For teams that want all memories shared by default, add to `.claude/settings.json`:

```json
{
  "twin-mind": {
    "share_memories": true
  }
}
```

With this config:
- `twin-mind remember "X"` → saves to `decisions.jsonl`
- `twin-mind remember "X" --local` → saves to `memory.mv2`

### Searching Across Both

Search automatically queries both local and shared memories:

```bash
twin-mind search "authentication"
# Returns results from: code, local memory, AND shared decisions

twin-mind search "Redis" --in memory
# Returns results from: local memory AND shared decisions
```

Results show the source:
```
📄 [1] auth.py (page 3/10)
   Score: 5.234 | Source: code

📤 [2] [arch] Chose JWT over sessions...
   Score: 4.123 | Source: shared

📝 [3] Need to check auth flow
   Score: 3.456 | Source: memory
```

### Git Workflow

Shared decisions integrate naturally with git:

```bash
# Developer A adds a decision
twin-mind remember "Using PostgreSQL for ACID compliance" --tag arch --share
git add .claude/decisions.jsonl
git commit -m "doc: record database choice"
git push

# Developer B adds another decision (in parallel)
twin-mind remember "API rate limiting set to 100 req/min" --tag config --share
git add .claude/decisions.jsonl
git commit -m "doc: record rate limit decision"
git pull --rebase  # Merges cleanly!
git push
```

### Why JSONL Format?

When two developers add decisions in parallel:

```jsonl
{"ts":"2024-01-22T10:30:00Z","msg":"Chose Redis","tag":"arch","author":"alice"}
{"ts":"2024-01-22T11:45:00Z","msg":"Fixed auth bug","tag":"bugfix","author":"bob"}
```

- **Line-based**: Each decision is one line
- **Append-only**: New decisions add new lines
- **Git-friendly**: Line additions merge without conflicts
- **Human-readable**: Plain JSON, easy to review in PRs

### What to Share vs Keep Local

| Share (team knowledge) | Keep Local (personal) |
|------------------------|----------------------|
| Architecture decisions | Personal TODOs |
| Technology choices | Debugging notes |
| API design rationale | Session context |
| Bug root causes | Work-in-progress ideas |
| Performance decisions | Temporary reminders |
| Security considerations | Machine-specific notes |

### Viewing Recent Decisions

```bash
twin-mind recent
# Shows both local and shared, most recent first

📤 [1] [arch] by alice
    Chose PostgreSQL for ACID compliance

📝 [2] Need to review PR #42
    (local, 2 hours ago)

📤 [3] [config] by bob
    API rate limiting set to 100 req/min
```

---

## Workflows

### Daily Development

```bash
# Find code
twin-mind search "authentication middleware" --in code

# Save personal note
twin-mind remember "TODO: refactor auth module" --tag todo

# Save team decision
twin-mind remember "Using Redis for sessions" --tag arch --share

# Check what's been recorded
twin-mind recent
```

### After Major Refactor

```bash
twin-mind reindex
# Memories preserved!
```

### Maintenance

```bash
twin-mind status                     # Check health
twin-mind prune memory --before 30d  # Clean old local memories
```

---

## Memory Tags

Use `--tag` when remembering to categorize:

| Tag | Use For |
|-----|---------|
| `arch` | Architecture decisions |
| `bugfix` | Bug resolutions |
| `feature` | Feature notes |
| `config` | Configuration choices |
| `todo` | Future work |
| `perf` | Performance notes |

---

## Claude Code Integration

Twin-mind installs as a Claude Code skill automatically. Claude will proactively search when you ask about:
- How existing code works
- Past decisions and their rationale
- Where things are implemented
- What changed recently

---

## Configuration

Optional `.claude/settings.json`:

```json
{
  "twin-mind": {
    "extensions": {
      "include": [".py", ".ts", ".tsx"],
      "exclude": [".min.js", ".bundle.js"]
    },
    "skip_dirs": ["node_modules", "dist", "custom_vendor"],
    "max_file_size": "500KB",
    "index": {
      "parallel": true,
      "parallel_workers": 4,
      "embedding_model": "bge-small",
      "adaptive_retrieval": true
    },
    "memory": {
      "share_memories": false,
      "dedupe": true
    }
  }
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `index.parallel` | `true` | Enable parallel file reading (3-6x faster) |
| `index.parallel_workers` | `4` | Number of parallel workers |
| `index.embedding_model` | `null` | Embedding model: `bge-small`, `bge-base`, `gte-large`, `openai` |
| `index.adaptive_retrieval` | `true` | Auto-determine optimal result count |
| `memory.share_memories` | `false` | Default memories to shared decisions |
| `memory.dedupe` | `true` | Enable deduplication for memories |

Configuration is optional - sensible defaults work out of box.

---

## Technical Details

### Powered by Memvid

Twin-Mind uses [Memvid](https://github.com/memvid/memvid) for code and local memory:

- **Single-file format** (`.mv2`) - No database setup
- **Sub-ms retrieval** - Native Rust core
- **Semantic search** - BM25 + vector embeddings

### Performance Features (v1.2.0)

- **Parallel ingestion** - 3-6x faster indexing with concurrent file reading
- **Adaptive retrieval** - Auto-determines optimal result count based on relevance
- **Deduplication** - SimHash prevents duplicate memories
- **Configurable embeddings** - Choose model based on speed/quality tradeoff
- **Doctor command** - Health checks, vacuum, and index maintenance

### File Types Indexed

```
.py .js .ts .tsx .jsx .java .kt .scala .go .rs .c .cpp .h .hpp
.cs .rb .php .swift .sql .sh .bash .yaml .yml .json .toml .xml
.html .css .scss .md .txt .vue .svelte .astro .prisma .graphql
.proto .tf
```

### Size Limits

- Max file size: 500KB (larger files skipped)
- Typical project: 1-5MB total

---

## Uninstall

```bash
twin-mind uninstall
```

Removes `~/.twin-mind/`, the skill directory, and the shell alias.

---

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/pego/twin-mind.git
cd twin-mind

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=scripts/twin_mind

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Linting and Formatting

```bash
# Check for linting issues
ruff check scripts/

# Auto-fix linting issues
ruff check scripts/ --fix

# Format code
ruff format scripts/

# Check formatting without changes
ruff format scripts/ --check
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. To run manually:

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run
```

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Memvid](https://github.com/memvid/memvid) - The memory engine powering Twin-Mind
- [Anthropic](https://anthropic.com) - Claude and the skills system

---

**If Twin-Mind saved you time, star the repo!**
