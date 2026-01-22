# Twin-Mind

**Dual memory for AI coding agents** - Codebase knowledge + Conversation memory with team-friendly sharing.

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
| `uninstall` | Remove twin-mind installation |

---

## Team Sharing

### Default: Local memories

```bash
twin-mind remember "Fixed auth bug" --tag bugfix
# Saved to memory.mv2 (not shared)
```

### Explicit sharing

```bash
twin-mind remember "Chose Redis for sessions" --tag arch --share
# Saved to decisions.jsonl (versioned, shared with team)
```

### Team configuration (share by default)

Add to `.claude/settings.json`:

```json
{
  "twin-mind": {
    "share_memories": true
  }
}
```

Now all `remember` commands go to `decisions.jsonl` by default. Use `--local` to override.

### Why JSONL?

When two developers add decisions in parallel:
```jsonl
{"ts":"2024-01-22T10:30:00Z","msg":"Chose Redis","tag":"arch","author":"alice"}
{"ts":"2024-01-22T11:45:00Z","msg":"Fixed auth bug","tag":"bugfix","author":"bob"}
```

Git merges line additions cleanly. No binary conflicts.

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
    "share_memories": false,
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

Twin-Mind uses [Memvid](https://github.com/memvid/memvid) for code and local memory:

- **Single-file format** (`.mv2`) - No database setup
- **Sub-ms retrieval** - Native Rust core
- **Semantic search** - BM25 + vector embeddings

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
