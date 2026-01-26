# Changelog

All notable changes to Twin-Mind will be documented in this file.

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
