# Changelog

All notable changes to Twin-Mind will be documented in this file.

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
