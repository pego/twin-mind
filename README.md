# 🧠 Twin-Mind

**Dual memory for AI coding agents** — Codebase knowledge + Conversation memory in two portable `.mv2` files.

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

Two files. Claude remembers everything — code AND decisions.

---

## 🏗️ Architecture

```
your-project/
└── .claude/
    ├── code.mv2      ← Codebase index (resettable)
    └── memory.mv2    ← Decisions/insights (persistent)
```

### Why Two Stores?

| | `code.mv2` | `memory.mv2` |
|---|---|---|
| **Contains** | Indexed source code | Decisions, bugs, insights |
| **Lifecycle** | Reset after refactors | Long-term persistent |
| **Git** | `.gitignore` | Commit & share |
| **Risk** | Stale after changes | Valuable context |

**Benefits:**
- 🔄 Reset code index without losing decisions
- 🎯 Prevent hallucinations from stale code
- 📦 Share project context with teammates
- ⚡ Sub-millisecond search (Memvid Rust core)

---

## 🚀 Quick Start

### Installation

```bash
# Install memvid SDK
pip install memvid-sdk

# Clone twin-mind
git clone https://github.com/pego/twin-mind.git
cd twin-mind
```

### Initialize in Your Project

```bash
cd /path/to/your/project

# Initialize twin-mind
python /path/to/twin-mind/scripts/twin-mind.py init

# Index your codebase
python /path/to/twin-mind/scripts/twin-mind.py index
```

### Create an Alias (Recommended)

```bash
# Add to ~/.bashrc or ~/.zshrc
alias twin-mind="python /path/to/twin-mind/scripts/twin-mind.py"

# Now use anywhere
twin-mind stats
```

---

## 📖 Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize both memory stores |
| `index` | Incremental index (git-based, fast) |
| `index --fresh` | Full rebuild from scratch |
| `index --status` | Preview what would be indexed |
| `remember <msg>` | Store a decision or insight |
| `search <query>` | Search both stores |
| `search <query> --context 10` | Show 10 lines context |
| `search <query> --full` | Show full file content |
| `ask <question>` | Semantic question (searches both) |
| `context <query>` | Combined code+memory for prompts |
| `recent` | Show recent memories |
| `stats` | Display statistics |
| `status` | Health check (index age, git state) |
| `reindex` | Reset code + fresh index |
| `prune memory --before 30d` | Remove old memories |
| `prune memory --tag session` | Remove by tag |

### Search Filters

```bash
# Search everything
twin-mind search "authentication"

# Search only code
twin-mind search "middleware" --in code

# Search only memories
twin-mind search "why we chose" --in memory

# More results
twin-mind search "database" --top-k 20

# JSON output (for scripts)
twin-mind search "api" --json
```

### Memory Management

```bash
# Store with category tag
twin-mind remember "Chose PostgreSQL for ACID compliance" --tag arch
twin-mind remember "Fixed race condition in OrderService" --tag bugfix
twin-mind remember "TODO: Add rate limiting" --tag todo

# Reset after refactor (safe - preserves memories)
twin-mind reset code
twin-mind index --fresh

# Reset memories (⚠️ permanent!)
twin-mind reset memory

# Export memories
twin-mind export --format md -o decisions.md
twin-mind export --format json -o backup.json
```

### Suggested Tags

| Tag | Use For |
|-----|---------|
| `arch` | Architecture decisions |
| `bugfix` | Bug resolutions |
| `feature` | Feature notes |
| `config` | Configuration choices |
| `todo` | Future work |
| `perf` | Performance notes |

---

## 🔄 Workflows

### New Project Setup

```bash
twin-mind init
twin-mind index
twin-mind remember "Project started - building a REST API for inventory management" --tag arch
```

### Daily Development

```bash
# Morning: Check what's in progress
twin-mind recent

# After fixing a bug
twin-mind remember "Fixed: Cart total was NaN when empty - added null check" --tag bugfix

# When making decisions
twin-mind remember "Using Redis for sessions instead of JWT - need server-side invalidation" --tag arch

# Finding code
twin-mind search "validation middleware" --in code
```

### After Major Refactor

```bash
# One command does it all
twin-mind reindex

# Or step by step:
twin-mind reset code
twin-mind index --fresh

# Verify
twin-mind status

# Memories still intact ✓
twin-mind recent
```

### Maintenance

```bash
# Check health
twin-mind status

# Clean up old session memories
twin-mind prune memory --before 30d --tag session

# Preview before pruning (dry run)
twin-mind prune memory --before 7d --dry-run
```

### Onboarding a Teammate

```bash
# Export your decisions
twin-mind export --format md -o project-context.md

# Or share the memory file directly
cp .claude/memory.mv2 /shared/

# Teammate imports
cp /shared/memory.mv2 .claude/
twin-mind index  # Index their local code
```

---

## 🔧 Claude Code Integration

### As a Skill

Copy the `twin-mind` folder to your Claude Code skills directory:

```bash
cp -r twin-mind ~/.claude/skills/
```

Claude will automatically use it when you ask about:
- "Remember this decision..."
- "Search the codebase for..."
- "What did we decide about..."
- "Index the project"

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

## ⚙️ Configuration

Add to `.claude/settings.json`:

```json
{
  "twin-mind": {
    "extensions": {
      "include": [".py", ".ts", ".tsx"],
      "exclude": [".min.js", ".bundle.js"]
    },
    "skip_dirs": ["node_modules", "dist", "custom_vendor"],
    "max_file_size": "500KB",
    "output": {
      "color": true,
      "verbose": false
    }
  }
}
```

Configuration is optional — sensible defaults are used if not specified.

### Global Flags

| Flag | Description |
|------|-------------|
| `--no-color` | Disable colored output |
| `-V, --version` | Show version |

Environment variable `NO_COLOR=1` also disables colors.

---

## 📊 Statistics

```bash
$ twin-mind stats

🧠 Twin-Mind Stats
=============================================
📄 Code Store:   .claude/code.mv2
   Size:         2.4 MB
   Files:        847

📝 Memory Store: .claude/memory.mv2
   Size:         124 KB
   Memories:     156
=============================================
```

---

## 🔬 Technical Details

### Powered by Memvid

Twin-Mind uses [Memvid](https://github.com/memvid/memvid) as its storage engine:

- **Single-file format** (`.mv2`) — No database setup
- **Sub-ms retrieval** — Native Rust core
- **Semantic search** — BM25 + vector embeddings
- **Portable** — Git commit, scp, share

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

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Memvid](https://github.com/memvid/memvid) — The memory engine powering Twin-Mind
- [Anthropic](https://anthropic.com) — Claude and the skills system
- [claude-brain](https://github.com/memvid/claude-brain) — Inspiration for this project

---

**If Twin-Mind saved you time, ⭐ star the repo!**
