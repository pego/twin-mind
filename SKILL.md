---
name: twin-mind
description: Codebase knowledge + conversation memory. Use proactively for code questions, past decisions, and finding implementations.
---

# Twin-Mind

Dual memory layer: **code index** (resettable) + **conversation memory** (persistent).

## Auto-Search Behavior

**Before answering, search twin-mind when the question involves:**
- Understanding existing code (how does X work, where is Y implemented)
- Past decisions (why did we choose X, what did we decide about Y)
- Finding implementations (where is X defined, which file handles Y)
- Debugging context (what changed recently, related error patterns)
- Architecture questions (how do these components connect)

**Skip searching for:**
- Direct action commands (fix this, add X, rename Y to Z)
- Clarifications about the current conversation
- Questions unrelated to the codebase
- Simple tasks that don't need context

## Installation

```bash
# One-command install
curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash

# Then restart terminal or run:
source ~/.zshrc  # or ~/.bashrc
```

First command in a new project auto-initializes.

## Commands

| Intent | Command |
|--------|---------|
| Find code | `twin-mind search "query" --in code` |
| Find decisions | `twin-mind search "query" --in memory` |
| Find both | `twin-mind search "query"` |
| Save insight | `twin-mind remember "message" --tag TAG` |
| Get context | `twin-mind context "topic"` |
| Check status | `twin-mind status` |
| Reindex | `twin-mind reindex` |
| Full reindex | `twin-mind index --fresh` |

## Tags for Memories

Use `--tag` when remembering to categorize:
- `arch` - Architecture decisions
- `bugfix` - Bug resolutions and root causes
- `feature` - Feature implementation notes
- `config` - Configuration choices
- `todo` - Future work items
- `perf` - Performance observations

## Examples

**User asks about code:**
```
User: "How does the authentication middleware work?"
> Run: twin-mind search "authentication middleware" --in code
> Use results to answer with specific file references
```

**User asks about past decision:**
```
User: "Why did we use Redis for sessions?"
> Run: twin-mind search "Redis sessions" --in memory
> Answer with the recorded rationale
```

**After making a decision:**
```
> Run: twin-mind remember "Chose PostgreSQL over MySQL for ACID compliance and JSON support" --tag arch
```

**Finding implementations:**
```
User: "Where is user validation implemented?"
> Run: twin-mind search "user validation" --in code
> Provide file paths and relevant code snippets
```

## Output Formats

For structured processing, use `--json` flag:
```bash
twin-mind search "query" --json
twin-mind context "topic" --json
```

## Architecture

```
~/.twin-mind/
├── venv/              # Isolated Python environment
├── twin-mind.py       # Main script
└── version.txt        # For updates

your-project/.claude/
├── code.mv2           # Codebase index (resettable)
├── memory.mv2         # Decisions/insights (persistent)
└── index_state.json   # Index metadata
```

**Why separate stores?**
- Code changes often > reset without losing decisions
- Prevents stale code from causing hallucinations
- Different retention policies for different data

## Workflows

### After a refactor
```bash
twin-mind reindex           # Reset and fresh index
# Memories preserved!
```

### Daily development
```bash
twin-mind remember "Fixed auth bug - was missing token refresh" --tag bugfix
twin-mind remember "Chose Redis for session store" --tag arch
```

### Maintenance
```bash
twin-mind status                     # Check health
twin-mind prune memory --before 30d  # Clean old memories
```

## Configuration

Optional `.claude/settings.json`:

```json
{
  "twin-mind": {
    "auto_search": true,
    "auto_index": true,
    "extensions": {
      "include": [],
      "exclude": [".min.js", ".bundle.js"]
    },
    "skip_dirs": ["node_modules", "dist", "vendor", ".git"],
    "max_file_size": "500KB"
  }
}
```

No configuration required - sensible defaults work out of box.

## Uninstall

```bash
twin-mind uninstall
```
