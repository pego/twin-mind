# Changelog

All notable changes to Twin-Mind will be documented in this file.

## [1.8.1] - 2026-02-19

### Fixed
- **Incremental index correctness**:
  - Removes stale entries for changed/deleted files before re-indexing
  - Saves total indexed frame count to `index-state.json` (status now reports accurate file counts)
  - Improves incremental output with stale-removal and total-count details

- **Search and context behavior**:
  - `search --json` now emits `file_path` for `file://...` code URIs
  - `context` now includes shared decisions (`decisions.jsonl`) in generated context output
  - `context --json` now reports `local_memory_results` and `shared_memory_results`

- **Prune tag matching**:
  - `prune memory --tag` now matches structured tags (e.g. `category:arch`) instead of title-only heuristics
  - Retains backward-compatible fallback matching for older entries

- **Install/uninstall consistency**:
  - `uninstall` now handles canonical skills directory `~/.agents/skills/twin-mind` and legacy `~/.claude/skills/twin-mind`
  - `install-skills` temp script permission reduced to `0700` to satisfy security checks

- **Packaging and release metadata consistency**:
  - `pyproject.toml` version and runtime version literals are synchronized to `1.8.1`
  - Runtime dependency updated to `memvid-sdk>=2.0.0` to match actual imports/install flow

## [1.8.0] - 2026-02-18

### Added
- **`twin-mind install-skills`**: New CLI command to symlink the twin-mind skill into
  all detected AI coding agents (delegates to `install-skills.sh`)
  - `--dry-run` — preview symlinks without making changes
  - `--update` — re-download `SKILL.md` before installing

- **`install-skills.sh`**: Standalone multi-IDE skill installer
  - Detects 14 agents: Claude Code, Cursor, Windsurf, Cline, Continue, Roo Code,
    Kilo Code, Kiro, Augment, GitHub Copilot, Gemini CLI, Codex, Goose, OpenCode
  - Symlinks `~/.agents/skills/twin-mind` into each detected agent's global skills directory
  - Detection by config directory presence or binary in PATH
  - Can be run standalone: `curl -sSL .../install-skills.sh | bash`

### Fixed
- **Version single source of truth**: `scripts/twin-mind.py` now imports `VERSION`
  from `twin_mind.constants` instead of hardcoding it; `upgrade.py` reads
  `constants.py` from GitHub instead of `twin-mind.py` for version detection
- **`install.sh`** no longer hardcodes the version in `version.txt` — reads it
  from the downloaded `constants.py` at install time
- **`upgrade`** now fetches `install-skills.sh` and `SKILL.md` alongside Python
  modules so they stay current after an upgrade

## [1.7.0] - 2026-02-18

### Added
- **Scope-Based Search** (`--scope PATH`): Limit code search results to a subdirectory
  - `twin-mind search "auth" --in code --scope src/auth/` filters hits to that path
  - Output header shows active scope: `Results for: '...' (in: code) [scope: src/auth/]`
  - No-op when `--scope` is omitted; all existing searches unchanged

- **Semantic Search for Shared Decisions**: `decisions.mv2` index built alongside `decisions.jsonl`
  - JSONL remains the source of truth (git-versioned, merge-friendly)
  - MV2 is gitignored and regeneratable from JSONL
  - `build_decisions_index()` rebuilds MV2 from scratch; called automatically on full reindex
  - `write_shared_memory()` incrementally updates MV2 when it already exists (best-effort)
  - `search_shared_memories()` uses semantic search when MV2 exists, lazily builds it if not, falls back to text matching
  - New `decisions.build_semantic_index` config key (default: `true`)

- **Size Monitoring & Warnings**: Post-operation warnings when stores exceed recommended thresholds
  - `twin-mind index` warns if `code.mv2` > 50 MB
  - `twin-mind remember` warns if `memory.mv2` > 15 MB or `decisions.jsonl` > 5 MB
  - Warning message includes `Run: twin-mind doctor` hint
  - Controlled by `maintenance.size_warnings` config key (default: `true`)
  - Thresholds configurable via `maintenance.code_max_mb`, `memory_max_mb`, `decisions_max_mb`

### Changed
- `DEFAULT_CONFIG` now includes `decisions` and `maintenance` sections
- `GITIGNORE_CONTENT` now lists `decisions.mv2` as gitignored

## [1.5.0] - 2025-01-26

### Added
- **Test Suite**: Comprehensive pytest tests with 121 test cases
  - Tests for config, filesystem, git, memory, output, and indexing modules
  - Command tests for init and remember
  - Shared fixtures in conftest.py
  - Coverage reporting support

- **GitHub Actions CI/CD**: Automated testing and linting pipeline
  - Lint job with ruff
  - Test matrix: ubuntu/macos × Python 3.8/3.10/3.12
  - Build verification job

- **Pre-commit Hooks**: Automated code quality checks
  - ruff linting with auto-fix
  - ruff formatting

- **Development Documentation**: README updated with dev setup instructions
  - How to install dev dependencies
  - How to run tests
  - How to lint and format code

### Changed
- **Complete Type Hints**: All 30 Python files now have full type annotations
  - Python 3.8 compatible using `typing` module
  - All public functions annotated with parameter and return types

- **Code Formatting**: All code formatted with ruff
  - Line length: 100 characters
  - Consistent style across all modules

### Fixed
- 64 linting issues identified and resolved by ruff
  - Import sorting
  - Unused imports and variables
  - Python 3.8+ compatibility fixes

## [1.4.0] - 2025-01-26

### Changed
- **Modularized Architecture**: Refactored 2,597-line monolith into a proper Python package
  - `twin-mind.py` is now a thin 37-line wrapper
  - Created `twin_mind/` package with 30 organized modules
  - Core modules: `constants`, `output`, `config`, `fs`, `git`, `memory`, `indexing`
  - State modules: `memvid_check`, `index_state`, `shared_memory`, `auto_init`
  - CLI module: `cli.py` with argparse setup and command dispatch
  - Commands package: 16 individual command modules in `commands/`
  - Clean separation of concerns and improved maintainability
  - No functional changes - all existing commands work identically

## [1.3.0] - 2025-01-22

### Added
- **Upgrade Command**: Self-updating capability
  - `upgrade` - Check for updates and upgrade if newer version available
  - `upgrade --check` - Only check for updates, don't install
  - `upgrade --force` - Skip confirmation prompt
  - Automatic backup before upgrading
  - Automatic rollback on failure
  - Updates twin-mind.py, version.txt, and SKILL.md

## [1.2.0] - 2025-01-22

### Added
- **Parallel Ingestion**: 3-6x faster indexing with concurrent file reading
  - Configurable via `index.parallel` (default: true)
  - `index.parallel_workers` to control concurrency (default: 4)
  - Automatically activates for >10 files

- **Configurable Embedding Models**: Choose model based on speed/quality tradeoff
  - `index.embedding_model` setting
  - Options: `bge-small`, `bge-base`, `gte-large`, `openai`, or null for default

- **Adaptive Retrieval**: Smarter search results
  - Auto-determines optimal result count based on relevance
  - Enabled by default via `index.adaptive_retrieval`
  - `--no-adaptive` flag to disable

- **Deduplication**: Prevent duplicate memories
  - SimHash-based deduplication
  - Enabled by default via `memory.dedupe`

- **Doctor Command**: Maintenance and diagnostics
  - `doctor` - Health check with recommendations
  - `doctor --vacuum` - Reclaim space from deleted entries
  - `doctor --rebuild` - Rebuild indexes after heavy pruning
  - Detects index staleness, bloat, and malformed entries

### Changed
- New configuration schema with `index.*` and `memory.*` namespaces
- Improved search with fallback for older memvid versions

## [1.1.0] - 2025-01-22

### Added
- **Configuration System**: Configure via `.claude/settings.json`
  - Custom file extensions to include/exclude
  - Custom directories to skip
  - Max file size limits
  - Color output control

- **Git-Based Incremental Indexing**: Fast updates using git diff
  - Only reindexes changed files
  - Tracks deleted files
  - Falls back to full index if not in git repo
  - `index --status` to preview changes

- **Prune Command**: Clean up old memories
  - `prune memory --before 30d` - by date
  - `prune memory --tag session` - by tag
  - `--dry-run` to preview
  - Auto-backup before pruning

- **Status Command**: Health check dashboard
  - Index age and file counts
  - Git state and commits behind
  - Memory store statistics

- **Context Command**: Generate combined context for prompts
  - Combines code and memory search
  - Token-limited output
  - JSON output support

- **Enhanced Search**
  - `--context N` - show N lines around matches
  - `--full` - show full file content
  - Structured JSON output with metadata
  - Stale index warnings

- **UX Improvements**
  - Colored output (disable with `--no-color` or `NO_COLOR=1`)
  - Progress bar during indexing
  - Better error messages with recovery suggestions
  - File locking for concurrent access safety

- **New Commands**
  - `reindex` - alias for reset code + index --fresh
  - `status` - health check dashboard
  - `context` - combined search for prompts

### Changed
- Version flag changed from `-v` to `-V`
- Index command now uses incremental mode by default
- Improved JSON output format for search results

### Fixed
- Better handling of corrupt memory stores
- Graceful degradation when git not available

## [1.0.0] - 2025-01-22

### Added
- Initial release
- Dual memory architecture (code + memory)
- Basic commands: init, index, remember, search, ask, recent, stats, reset, export
- Memory tagging support
- Markdown and JSON export
