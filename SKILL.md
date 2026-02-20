---
name: twin-mind
description: |
  Codebase knowledge + conversation memory. Use proactively for code questions, past decisions, and finding implementations.

  TRIGGER PHRASES - Invoke this skill when user asks:
  - "where is", "which file", "find the", "locate", "show me"
  - "how does", "what does", "explain how", "walk me through"
  - "why did we", "what did we decide", "what was the reason"
  - "remember when", "we discussed", "previously", "last time"
  - "architecture", "implementation", "codebase", "pattern"

  DEFAULT: When uncertain if context would help, search first - it's fast and non-destructive.
---

# Twin-Mind

Dual memory layer: **code index** (resettable) + **conversation memory** (local + shared).

---

## IMPORTANT: When to Use This Skill

### Trigger Keywords (Search Automatically)

**Location queries:**
- "where", "which file", "find", "locate", "show me", "look for"

**Understanding queries:**
- "how does", "what does", "explain", "walk through", "understand"

**History/Memory queries:**
- "why did we", "what was", "when did", "who decided", "remember"
- "we discussed", "previously", "last time", "earlier"

**Architecture queries:**
- "how do these connect", "what's the pattern", "architecture"
- "implementation", "structure", "design"

### Question → Command Mapping

| User Question Pattern | Command to Run |
|-----------------------|----------------|
| "Where is X implemented?" | `twin-mind search "X" --in code` |
| "How does X work?" | `twin-mind search "X" --in code` |
| "Why did we choose X?" | `twin-mind search "X" --in memory` |
| "What did we decide about X?" | `twin-mind search "X" --in memory` |
| "What do we know about X?" | `twin-mind search "X"` |
| "Find anything related to X" | `twin-mind search "X"` |

### When NOT to Use (Skip Searching)

- Direct action commands without context needs: "fix this typo", "add a button"
- Questions about the current conversation: "what did I just say?"
- Generic programming questions unrelated to THIS codebase: "what's Python syntax for X?"
- Simple tasks with explicit instructions: "rename variable foo to bar"

### Default Behavior

**When uncertain whether context would help → Search first.**

Twin-mind searches are fast and non-destructive. When in doubt, a quick search provides context that improves answers. It's better to search and find nothing useful than to miss important context.

---

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
| Find entities | `twin-mind search "query" --in entities` |
| Find both | `twin-mind search "query"` |
| Find entity symbol | `twin-mind entities find "<symbol>"` |
| Find callers | `twin-mind entities callers "<symbol>"` |
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
├── entities.sqlite    # Entity graph (gitignored, regeneratable)
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
