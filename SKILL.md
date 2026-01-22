---
name: twin-mind
description: Dual-memory system for AI coding agents - separates codebase knowledge (resettable) from conversation memory (persistent). Use when asked to "remember this", "search the codebase", "find where X is implemented", "what did we decide", "reset the code index", "index the project", or any request involving project context, past decisions, code search, or memory management.
---

# Twin-Mind

Dual-memory layer: **code knowledge** (resettable) + **conversation memory** (persistent).

## Architecture

```
.claude/
├── code.mv2      # Codebase index - reset after refactors
└── memory.mv2    # Decisions/insights - long-term persistent
```

**Why separate?**
- Code changes often → reset without losing decisions
- Prevents stale code from causing hallucinations
- Different retention policies for different data

## Setup

```bash
pip install memvid-sdk --break-system-packages

python scripts/twin-mind.py init      # Creates both stores
python scripts/twin-mind.py index     # Index codebase
```

## Commands

| Command | Purpose |
|---------|---------|
| `init` | Initialize both stores |
| `index` | Incremental index (git-based) |
| `index --fresh` | Full reindex from scratch |
| `index --status` | Preview what would be indexed |
| `remember <msg>` | Save decision/insight |
| `search <query>` | Search all |
| `search <query> --in code` | Search only code |
| `search <query> --context 10` | Show 10 lines context |
| `search <query> --full` | Show full file content |
| `ask <question>` | Semantic query |
| `context <query>` | Generate combined context for prompts |
| `recent` | Recent memories |
| `stats` | Show statistics |
| `status` | Health check (index age, git state) |
| `reindex` | Reset code and fresh index |
| `reset code` | Clear code index |
| `reset memory` | Clear memories (⚠️ permanent) |
| `prune memory --before 30d` | Remove old memories |
| `prune memory --tag session` | Remove by tag |
| `export --format md` | Export memories to markdown |

### Global Flags

| Flag | Purpose |
|------|---------|
| `--no-color` | Disable colored output |
| `-V, --version` | Show version |

## Workflows

### After a refactor
```bash
twin-mind reset code           # Clear stale code
twin-mind index --fresh        # Reindex everything
# Memories preserved! ✓
```

### Daily development
```bash
twin-mind remember "Fixed auth bug - was missing token refresh" --tag bugfix
twin-mind remember "Chose Redis for session store" --tag architecture
twin-mind search "authentication" --in code
```

### Understanding code
```bash
twin-mind ask "How does payment processing work?"
twin-mind search "database connection" --in code
```

### Export for sharing
```bash
twin-mind export --format md -o decisions.md
twin-mind export --format json -o memories.json
```

### Maintenance
```bash
twin-mind status                    # Check health
twin-mind prune memory --before 30d # Clean old memories
twin-mind reindex                   # Full reset and reindex
```

### Generate context for prompts
```bash
twin-mind context "authentication"           # Combined code+memory
twin-mind context "API design" --json        # Structured JSON
```

## Configuration

Add to `.claude/settings.json`:

```json
{
  "twin-mind": {
    "extensions": {
      "include": [".py", ".ts"],
      "exclude": [".min.js"]
    },
    "skip_dirs": ["node_modules", "dist", "custom_dir"],
    "max_file_size": "500KB",
    "output": {
      "color": true,
      "verbose": false
    }
  }
}
```

## Memory Tags

Use `--tag` / `-t` to categorize:
- `arch` — Architecture decisions
- `bugfix` — Bug resolutions  
- `feature` — Feature notes
- `config` — Configuration choices
- `todo` — Future work

## Advanced

See `references/advanced.md` for SDK usage and hooks integration.
