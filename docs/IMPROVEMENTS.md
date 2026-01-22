# Twin-Mind Improvements Roadmap

Based on analysis of [Memvid documentation](https://docs.memvid.com/) and performance tuning guide.

## Overview

Twin-Mind currently uses basic Memvid features. This document outlines improvements to leverage Memvid's full capabilities for better performance and functionality.

---

## Phase 1: Performance Wins

### 1.1 Parallel Ingestion
**Status:** ✅ Completed (v1.2.0)
**Impact:** 3-6x faster indexing
**Effort:** Low

Enable concurrent file processing during indexing.

```python
# Before: Sequential
for file in files:
    mem.put(content)

# After: Parallel file reading with ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=num_workers) as executor:
    futures = {executor.submit(_read_file_content, fp, codebase_root): fp for fp in files}
```

**Configuration:**
```json
{
  "twin-mind": {
    "index": {
      "parallel": true,
      "parallel_workers": 4
    }
  }
}
```

---

### 1.2 Configurable Embedding Model
**Status:** ✅ Completed (v1.2.0)
**Impact:** Flexibility + performance
**Effort:** Medium

Support multiple embedding models based on use case:

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `bge-small` | 33MB | Fastest | Good | Prototyping, small projects |
| `bge-base` | 110MB | Medium | Better | Production (default) |
| `gte-large` | 335MB | Slower | Best | Maximum quality |
| `ollama/nomic` | Local | Varies | Good | Offline/privacy |
| `openai` | API | Fast | Excellent | Cloud, highest quality |

**Configuration:**
```json
{
  "twin-mind": {
    "index": {
      "embedding_model": "bge-small"
    }
  }
}
```

---

### 1.3 Adaptive Retrieval
**Status:** ✅ Completed (v1.2.0)
**Impact:** Better search results
**Effort:** Low

Let Memvid auto-determine optimal result count based on relevance instead of fixed `top_k`.

```python
# Before: Fixed count
response = mem.find(query, k=top_k)

# After: Adaptive (enabled by default)
response = mem.find(query, adaptive=True, k=top_k)
```

**Configuration:**
```json
{
  "twin-mind": {
    "index": {
      "adaptive_retrieval": true
    }
  }
}
```

**CLI:** Use `--no-adaptive` to disable for predictable latency.

---

### 1.4 Deduplication (SimHash)
**Status:** ✅ Completed (v1.2.0)
**Impact:** Cleaner memory, smaller files
**Effort:** Low

Automatically prevent duplicate/near-duplicate memories.

```python
mem.put(memory_content, dedupe=True)
```

**Configuration:**
```json
{
  "twin-mind": {
    "memory": {
      "dedupe": true
    }
  }
}
```

---

### 1.5 Doctor Command
**Status:** ✅ Completed (v1.2.0)
**Impact:** Maintenance hygiene
**Effort:** Low

Add maintenance commands for index health.

```bash
twin-mind doctor              # Health check + recommendations
twin-mind doctor --vacuum     # Reclaim deleted space
twin-mind doctor --rebuild    # Rebuild indexes (after >20% deletions)
```

**Features:**
- Checks code store, memory store, and shared decisions
- Detects index staleness (commits behind HEAD)
- Identifies bloated stores
- Finds malformed JSONL entries
- Provides actionable recommendations

---

## Phase 2: Memory Quality

### 2.1 Scope-Based Search
**Status:** 🔲 Not Started
**Impact:** Faster targeted queries
**Effort:** Low

Enable directory scoping to reduce search space.

```bash
twin-mind search "auth" --in code --scope src/auth/
```

---

### 2.2 Semantic Search for Shared Decisions
**Status:** 🔲 Not Started
**Impact:** Better decision discovery
**Effort:** Medium

Build `decisions.mv2` index alongside `decisions.jsonl`:
- JSONL remains source of truth (git-mergeable)
- MV2 provides semantic search capability
- Auto-sync on init/index

---

### 2.3 Size Monitoring & Warnings
**Status:** 🔲 Not Started
**Impact:** Better UX
**Effort:** Low

Warn when indexes exceed recommended sizes:

| Store | Recommended Max |
|-------|-----------------|
| Personal notes | 10-15MB |
| Single project | 15-25MB |
| Documentation | 25-35MB |

---

## Phase 3: Advanced Features

### 3.1 Entity Extraction (Knowledge Graph)
**Status:** 🔲 Not Started
**Impact:** Powerful code queries
**Effort:** Medium

Extract code entities (classes, functions, types) with relationships.

```python
# Index with entity extraction
mem.put(content, extract_entities=True)

# Query relationships
mem.query_entities("authenticate", relationship="calls")
```

**Enables:**
- "What functions call `authenticate`?"
- "What classes inherit from `BaseController`?"
- O(1) entity lookups via SlotIndex

---

### 3.2 Time-Travel Debugging
**Status:** 🔲 Not Started
**Impact:** Better debugging
**Effort:** Medium

Record and replay agent sessions.

```python
mem.start_session("debug-auth-bug")
# ... searches happen ...
mem.end_session()

# Later
mem.replay_session("debug-auth-bug")
```

**Use cases:**
- Debug why Claude made certain decisions
- A/B test different approaches
- Audit trail for compliance

---

### 3.3 Visual Content Support (CLIP)
**Status:** 🔲 Not Started
**Impact:** Index diagrams/screenshots
**Effort:** Medium

```python
mem.put_image("architecture.png", tags=["arch"])
mem.find_visual("database schema")
```

---

### 3.4 Encryption
**Status:** 🔲 Not Started
**Impact:** Enterprise security
**Effort:** Low

AES-256-GCM encryption for sensitive codebases.

```python
mem.create("code.mv2", password="secret", encrypt=True)
```

---

### 3.5 PII Detection & Masking
**Status:** 🔲 Not Started
**Impact:** Privacy compliance
**Effort:** Low

Auto-detect and mask sensitive data in memories.

---

### 3.6 Framework Integrations
**Status:** 🔲 Not Started
**Impact:** Broader ecosystem
**Effort:** Medium

Support LangChain, LlamaIndex retrievers.

```python
from langchain.retrievers import MemvidRetriever
retriever = MemvidRetriever(path=".claude/code.mv2")
```

---

## Configuration Schema (Target)

```json
{
  "twin-mind": {
    "code_index": {
      "mode": "auto",
      "embedding_model": "bge-small",
      "parallel": true,
      "adaptive_retrieval": true
    },
    "memory": {
      "dedupe": true,
      "extract_entities": false
    },
    "decisions": {
      "build_semantic_index": true
    },
    "maintenance": {
      "auto_vacuum": false,
      "size_warnings": true
    }
  }
}
```

---

## Performance Benchmarks (Target)

| Metric | Current | After Phase 1 |
|--------|---------|---------------|
| Index 1000 files | ~60s | ~15s |
| Code search | ~35ms | ~25ms |
| Memory search | ~35ms | ~25ms |
| Index size | 100% | ~70% (with bge-small) |

---

## References

- [Memvid Docs](https://docs.memvid.com/)
- [Performance Tuning](https://docs.memvid.com/concepts/performance-tuning)
