---
name: twin-mind
description: Codebase knowledge + conversation memory. Use proactively for code questions, past decisions, and finding implementations.
---

# Twin-Mind

Dual memory layer: **code index** (resettable) + **conversation memory** (local + shared).

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
| Save insight (local) | `twin-mind remember "message" --tag TAG` |
| Save insight (shared) | `twin-mind remember "message" --share` |
| Get context | `twin-mind context "topic"` |
| Check status | `twin-mind status` |
| Reindex | `twin-mind reindex` |

## Memory Storage

Twin-mind supports two types of memory storage:

| Storage | File | Versioned | Use Case |
|---------|------|-----------|----------|
| **Local** | `memory.mv2` | No | Personal notes, session context |
| **Shared** | `decisions.jsonl` | Yes | Team decisions, architecture choices |

**Default behavior:**
- `twin-mind remember "X"` → saves to local `memory.mv2`
- `twin-mind remember "X" --share` → saves to shared `decisions.jsonl`

**Team configuration** (everyone shares by default):
```json
{
  "twin-mind": {
    "share_memories": true
  }
}
```

When `share_memories: true`, all memories go to `decisions.jsonl` (can override with `--local`).

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

**After making a team decision:**
```
> Run: twin-mind remember "Chose PostgreSQL over MySQL for ACID compliance" --tag arch --share
```

**Personal note:**
```
> Run: twin-mind remember "Need to refactor auth module tomorrow" --tag todo --local
```

## Architecture

```
your-project/.claude/
├── code.mv2           # Codebase index (gitignored)
├── memory.mv2         # Local memories (gitignored)
├── decisions.jsonl    # Shared decisions (versioned, mergeable)
└── index-state.json   # Index metadata (gitignored)
```

**Why this structure?**
- `decisions.jsonl` uses JSONL format = git can merge parallel additions
- Local memories stay private, shared decisions are team knowledge
- Code index is regeneratable, no need to version

## Configuration

Optional `.claude/settings.json`:

```json
{
  "twin-mind": {
    "share_memories": false,
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
