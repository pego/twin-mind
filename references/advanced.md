# Twin-Mind - Advanced Reference

## Architecture

```
your-project/
├── .claude/
│   ├── code.mv2      ← Codebase index (resettable)
│   └── memory.mv2    ← Decisions/insights (persistent)
├── src/
├── tests/
└── ...
```

**Two separate stores by design:**
- `code.mv2` — Refresh after refactors without losing context
- `memory.mv2` — Long-term decisions survive code changes

## Python SDK Direct Usage

```python
from memvid_sdk import Memvid, PutOptions, SearchRequest

# Open specific store
code_brain = Memvid.open(".claude/code.mv2")
memory_brain = Memvid.open(".claude/memory.mv2")

# Search code
req = SearchRequest(
    query="authentication middleware",
    top_k=5,
    filter_tags={"language": "python"}
)
code_results = code_brain.search(req)

# Store a memory
opts = PutOptions.builder() \
    .title("Architecture Decision: Database") \
    .uri("twin-mind://decision/database") \
    .tag("category", "architecture") \
    .tag("timestamp", "2024-01-15T10:30:00") \
    .build()

memory_brain.put_bytes_with_options(
    b"Chose PostgreSQL for ACID compliance and JSON support",
    opts
)
memory_brain.commit()
```

## Search Strategies

### Find code implementations
```bash
twin-mind search "authentication middleware" --in code
twin-mind search "database connection pool" --in code
twin-mind search "error handling" --in code -k 20
```

### Find past decisions
```bash
twin-mind search "why we chose" --in memory
twin-mind search "architecture" --in memory
twin-mind recent --n 50
```

### Combined search (default)
```bash
twin-mind search "JWT tokens"
twin-mind ask "How does authentication work?"
```

## Reset Workflows

### After major refactor
```bash
# Code is stale, but keep decisions
twin-mind reset code
twin-mind index --fresh
twin-mind stats
```

### Fresh start on project
```bash
twin-mind reset all --force
twin-mind init
twin-mind index
```

### Prune old memories
```bash
# Remove memories older than 30 days
twin-mind prune memory --before 30d

# Remove by date
twin-mind prune memory --before 2024-01-01
```

## Hooks Integration

Auto-capture session context in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [{
          "type": "command",
          "command": "twin-mind remember \"Starting task: $CLAUDE_TASK\" --tag session",
          "timeout": 5
        }]
      }
    ],
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

## Team Sharing

```bash
# Share decisions (not code - they can index their own)
cp .claude/memory.mv2 /shared/project-context.mv2

# Teammate imports
cp /shared/project-context.mv2 .claude/memory.mv2
twin-mind index  # Index their local code
```

## Git Strategy

Recommended `.gitignore` additions:

```gitignore
# Twin-Mind: Ignore code index (machine-specific)
.claude/code.mv2

# Twin-Mind: Track memory (shared decisions)
!.claude/memory.mv2
```

This way:
- Code index is rebuilt locally by each developer
- Decisions and context are shared via git

## Best Practices

1. **Reset code.mv2 after refactors** — Prevents hallucinations from stale code
2. **Never casually reset memory.mv2** — Decisions are hard-won knowledge
3. **Tag consistently** — `arch`, `bugfix`, `feature`, `config`, `todo`
4. **Export periodically** — `twin-mind export -o backup.md` for safety
5. **Prune session noise** — Remove auto-captured edits after milestones

## Troubleshooting

**Search returns stale results:**
```bash
twin-mind reset code
twin-mind index --fresh
```

**Memory too large:**
```bash
twin-mind stats
twin-mind prune memory --before 60d
# Or export and reset
twin-mind export -o archive.md
twin-mind reset memory
```

**Conflicting info in results:**
- Check if code was reindexed after refactor
- Check memory timestamps for outdated decisions
- Use `--in code` or `--in memory` to isolate sources

**Performance issues:**
- Check file count with `twin-mind stats`
- Consider excluding large generated files
- Split very large projects into sub-indexes
