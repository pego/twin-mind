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
| `index` | Index codebase (append) |
| `index --fresh` | Reindex from scratch |
| `remember <msg>` | Save decision/insight |
| `search <query>` | Search all |
| `search <query> --in code` | Search only code |
| `search <query> --in memory` | Search only memories |
| `ask <question>` | Semantic query |
| `recent` | Recent memories |
| `stats` | Show statistics |
| `reset code` | Clear code index |
| `reset memory` | Clear memories (⚠️ permanent) |
| `export --format md` | Export memories to markdown |

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

## Memory Tags

Use `--tag` / `-t` to categorize:
- `arch` — Architecture decisions
- `bugfix` — Bug resolutions  
- `feature` — Feature notes
- `config` — Configuration choices
- `todo` — Future work

## Advanced

See `references/advanced.md` for SDK usage and hooks integration.
