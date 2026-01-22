# Twin-Mind

**Dual memory for AI coding agents** - Codebase knowledge + Conversation memory in two portable `.mv2` files.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Memvid](https://img.shields.io/badge/powered%20by-memvid-orange.svg)](https://github.com/memvid/memvid)

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

Two files. Claude remembers everything - code AND decisions.

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
~/.twin-mind/
├── venv/              # Isolated Python environment
├── twin-mind.py       # Main script
└── version.txt        # Version info

your-project/.claude/
├── code.mv2           # Codebase index (resettable)
├── memory.mv2         # Decisions/insights (persistent)
└── index_state.json   # Index metadata
```

### Why Two Stores?

| | `code.mv2` | `memory.mv2` |
|---|---|---|
| **Contains** | Indexed source code | Decisions, bugs, insights |
| **Lifecycle** | Reset after refactors | Long-term persistent |
| **Git** | `.gitignore` | Commit & share |
| **Risk** | Stale after changes | Valuable context |

**Benefits:**
- Reset code index without losing decisions
- Prevent hallucinations from stale code
- Share project context with teammates
- Sub-millisecond search (Memvid Rust core)

---

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `search <query>` | Search both stores |
| `search <query> --in code` | Search only code |
| `search <query> --in memory` | Search only memories |
| `remember <msg>` | Store a decision or insight |
| `remember <msg> --tag TAG` | Store with category |
| `context <query>` | Combined code+memory for prompts |
| `status` | Health check (index age, git state) |
| `stats` | Display statistics |
| `recent` | Show recent memories |

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
| `init` | Initialize both memory stores |
| `reset code` | Clear code index |
| `reset memory` | Clear memories (permanent) |
| `prune memory --before 30d` | Remove old memories |
| `prune memory --tag session` | Remove by tag |
| `export --format md` | Export memories to markdown |
| `uninstall` | Remove twin-mind installation |

### Global Flags

| Flag | Description |
|------|-------------|
| `--no-color` | Disable colored output |
| `-V, --version` | Show version |

---

## Workflows

### Daily Development

```bash
# Find code
twin-mind search "authentication middleware" --in code

# Save decisions
twin-mind remember "Fixed race condition in OrderService" --tag bugfix
twin-mind remember "Using Redis for sessions instead of JWT" --tag arch

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
twin-mind prune memory --before 30d  # Clean old memories
```

### Onboarding a Teammate

```bash
# Export your decisions
twin-mind export --format md -o decisions.md

# Or share the memory file directly
cp .claude/memory.mv2 /shared/

# Teammate copies it
cp /shared/memory.mv2 .claude/
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

### With Hooks (Auto-capture)

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "twin-mind remember \"Modified: $CLAUDE_FILE_PATH\" --tag session",
          "timeout": 5
        }]
      }
    ]
  }
}
```

---

## Configuration

Optional `.claude/settings.json`:

```json
{
  "twin-mind": {
    "auto_search": true,
    "auto_index": true,
    "extensions": {
      "include": [".py", ".ts", ".tsx"],
      "exclude": [".min.js", ".bundle.js"]
    },
    "skip_dirs": ["node_modules", "dist", "custom_vendor"],
    "max_file_size": "500KB"
  }
}
```

Configuration is optional - sensible defaults work out of box.

---

## Technical Details

### Powered by Memvid

Twin-Mind uses [Memvid](https://github.com/memvid/memvid) as its storage engine:

- **Single-file format** (`.mv2`) - No database setup
- **Sub-ms retrieval** - Native Rust core
- **Semantic search** - BM25 + vector embeddings
- **Portable** - Git commit, scp, share

### File Types Indexed

```
.py .js .ts .tsx .jsx .java .kt .scala .go .rs .c .cpp .h .hpp
.cs .rb .php .swift .sql .sh .bash .yaml .yml .json .toml .xml
.html .css .scss .md .txt .vue .svelte .astro .prisma .graphql
.proto .tf
```

### Directories Skipped

```
node_modules .git __pycache__ .venv venv env .idea .vscode dist
build target .next .nuxt coverage .pytest_cache .mypy_cache vendor
.claude .terraform .serverless cdk.out .aws-sam
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
