# Claude Code Integration Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make twin-mind seamlessly integrated with Claude Code - one-command install, auto-initialization, and intelligent auto-search.

**Architecture:** Global install with isolated venv at `~/.twin-mind/`, per-project stores in `.claude/`, skill-based integration with semantic auto-search.

**Tech Stack:** Python 3.8+, memvid-sdk, bash installer, Claude Code skills

---

## 1. Installation System

### 1.1 One-Command Install

```bash
curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash
```

### 1.2 Install Script Behavior

1. Check Python 3.8+ available
2. Create `~/.twin-mind/` directory
3. Create isolated venv at `~/.twin-mind/venv/`
4. Install `memvid-sdk` into venv
5. Download `twin-mind.py` to `~/.twin-mind/`
6. Create skill directory `~/.claude/skills/twin-mind/`
7. Install `SKILL.md` to skill directory
8. Detect shell (zsh/bash) and add alias to config
9. Print success message with next steps

### 1.3 Directory Structure

```
~/.twin-mind/
├── venv/                 # Isolated Python environment
│   ├── bin/
│   │   ├── python
│   │   └── pip
│   └── lib/
├── twin-mind.py          # Main script
└── version.txt           # For update checks

~/.claude/skills/twin-mind/
└── SKILL.md              # Claude Code skill definition
```

### 1.4 Shell Alias

```bash
# Added to ~/.zshrc or ~/.bashrc
alias twin-mind="~/.twin-mind/venv/bin/python ~/.twin-mind/twin-mind.py"
```

### 1.5 Uninstall Command

```bash
twin-mind uninstall
# Removes ~/.twin-mind/, skill directory, and alias from shell config
```

---

## 2. Per-Project Auto-Initialization

### 2.1 Behavior

When any twin-mind command runs in a directory without `.claude/`:

```bash
cd ~/my-project
twin-mind search "auth"

# Output:
📂 No twin-mind setup detected in this project.
   Initializing...
   ✅ Created .claude/code.mv2
   ✅ Created .claude/memory.mv2
   📂 Indexing codebase... (47 files)
   ✅ Ready!

🔍 Results for: 'auth'
...
```

### 2.2 Auto-Init Guards

Skip auto-init for:
- Home directory (`~`)
- System directories (`/usr`, `/etc`, `/var`, etc.)
- Root directory (`/`)
- Directories with no code files detected

### 2.3 Per-Project Structure

```
~/my-project/
└── .claude/
    ├── code.mv2           # Codebase index (resettable)
    ├── memory.mv2         # Decisions/insights (persistent)
    ├── index_state.json   # Index metadata
    └── settings.json      # Optional project config
```

---

## 3. Skill Design

### 3.1 Skill Location

`~/.claude/skills/twin-mind/SKILL.md`

### 3.2 Skill Content

```markdown
---
name: twin-mind
description: Codebase knowledge + conversation memory. Use proactively
             for code questions, past decisions, and finding implementations.
---

# Twin-Mind

Dual memory layer: **code index** (resettable) + **conversation memory** (persistent).

## Auto-Search Behavior

**Before answering, search twin-mind when the question involves:**
- Understanding existing code (how does X work, where is Y implemented)
- Past decisions (why did we choose X, what did we decide about Y)
- Finding implementations (where is X defined, which file handles Y)
- Debugging context (what changed recently, related error patterns)

**Skip searching for:**
- Direct action commands (fix this, add X, rename Y to Z)
- Clarifications about the current conversation
- Questions unrelated to the codebase
- Simple tasks that don't need context

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
→ Run: twin-mind search "authentication middleware" --in code
→ Use results to answer with specific file references
```

**User asks about past decision:**
```
User: "Why did we use Redis for sessions?"
→ Run: twin-mind search "Redis sessions" --in memory
→ Answer with the recorded rationale
```

**After making a decision:**
```
→ Run: twin-mind remember "Chose PostgreSQL over MySQL for ACID compliance and JSON support" --tag arch
```

## Output Formats

For structured processing, use `--json` flag:
```bash
twin-mind search "query" --json
twin-mind context "topic" --json
```
```

---

## 4. Configuration

### 4.1 Per-Project Settings

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

### 4.2 Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `auto_search` | `true` | Claude auto-searches before answering code/decision questions |
| `auto_index` | `true` | Auto-reindex when files changed since last index |
| `extensions.include` | `[]` | Additional extensions to index |
| `extensions.exclude` | `[]` | Extensions to skip |
| `skip_dirs` | common | Additional directories to skip |
| `max_file_size` | `"500KB"` | Skip files larger than this |

### 4.3 Defaults Work Out of Box

No configuration required - sensible defaults for most projects.

---

## 5. Implementation Tasks

### Task 1: Create Install Script
- Create `install.sh` at repo root
- Implement venv creation and dependency install
- Shell detection and alias setup
- Skill file installation
- Error handling and rollback

### Task 2: Add Auto-Init to CLI
- Modify twin-mind.py to detect missing `.claude/`
- Implement auto-init with guards
- Add progress output during auto-init
- Skip dangerous directories

### Task 3: Update Skill File
- Rewrite SKILL.md with auto-search guidance
- Add command reference
- Add examples for common scenarios

### Task 4: Add Uninstall Command
- New `uninstall` subcommand
- Remove ~/.twin-mind/
- Remove skill directory
- Clean alias from shell config

### Task 5: Update Documentation
- Update README.md with new install process
- Update CHANGELOG.md
- Update SKILL.md (separate from installed version)

---

## 6. Success Criteria

1. **Install:** Single curl command sets up everything
2. **First use:** `twin-mind search X` in new project just works
3. **Claude integration:** Claude proactively searches when appropriate
4. **Zero config:** Works without any settings.json
5. **Clean uninstall:** One command removes everything
