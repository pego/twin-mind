#!/bin/bash
#
# Twin-Mind Skills Installer
# Installs the twin-mind skill following the vercel-labs/skills convention:
#
#   Canonical dir:  ~/.agents/skills/twin-mind/   (contains SKILL.md)
#   Per-IDE links:  ~/.claude/skills/twin-mind  ->  ~/.agents/skills/twin-mind
#                   ~/.cursor/skills/twin-mind  ->  ~/.agents/skills/twin-mind
#                   ... (one symlink per detected agent)
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install-skills.sh | bash
#   ./install-skills.sh            # install for all detected agents
#   ./install-skills.sh --dry-run  # preview without making changes
#   ./install-skills.sh --update   # refresh SKILL.md, then reinstall
#

set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://raw.githubusercontent.com/pego/twin-mind/main"
SKILL_NAME="twin-mind"
# Canonical location — matches vercel-labs/skills convention
AGENTS_SKILLS_DIR="$HOME/.agents/skills"
SKILL_CANONICAL="$AGENTS_SKILLS_DIR/$SKILL_NAME"   # the directory being symlinked

# ── Helpers ───────────────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}$1${NC}"; }
success() { echo -e "${GREEN}  ✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}  ! $1${NC}"; }
skip()    { echo -e "  - $1"; }

DRY_RUN=false
UPDATE=false

for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --update)  UPDATE=true  ;;
    esac
done

# ── Download helper ───────────────────────────────────────────────────────────
download() {
    local url=$1 dest=$2
    if command -v curl >/dev/null 2>&1; then
        curl -sSL "$url" -o "$dest"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$dest"
    else
        echo -e "${RED}Error: neither curl nor wget found.${NC}"
        exit 1
    fi
}

# ── Detection ─────────────────────────────────────────────────────────────────
detected() {
    local check="$1"
    [ -d "$check" ] || command -v "$check" >/dev/null 2>&1
}

# ── Install symlink for one agent ─────────────────────────────────────────────
# Creates: <skills_dir>/twin-mind  ->  ~/.agents/skills/twin-mind
install_skill() {
    local label="$1"
    local skills_dir="$2"
    local target="$skills_dir/$SKILL_NAME"

    if $DRY_RUN; then
        echo -e "  ${BLUE}[dry-run]${NC} $label"
        echo -e "           $target -> $SKILL_CANONICAL"
        return
    fi

    mkdir -p "$skills_dir"

    if [ -L "$target" ]; then
        # Replace existing symlink
        rm "$target"
    elif [ -d "$target" ] && [ ! -L "$target" ]; then
        # Real directory — don't clobber, skip with warning
        warn "$label: $target is a real directory, skipping"
        return
    fi

    ln -s "$SKILL_CANONICAL" "$target"
    success "$label  ($target)"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}Twin-Mind — Skills Installer${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    $DRY_RUN && warn "Dry-run mode — no changes will be made" && echo ""

    # ── Ensure canonical skill directory and SKILL.md exist ───────────────────
    if ! $DRY_RUN && { $UPDATE || [ ! -f "$SKILL_CANONICAL/SKILL.md" ]; }; then
        info "Downloading SKILL.md → $SKILL_CANONICAL/"
        mkdir -p "$SKILL_CANONICAL"
        download "$REPO_URL/SKILL.md" "$SKILL_CANONICAL/SKILL.md"
        success "Saved to $SKILL_CANONICAL/SKILL.md"
        echo ""
    fi

    # ── Detect and install ────────────────────────────────────────────────────
    info "Detecting installed agents..."
    echo ""

    installed=0
    skipped=0

    try() {
        local label="$1" detection="$2" skills_dir="$3"
        if detected "$detection"; then
            install_skill "$label" "$skills_dir"
            installed=$((installed + 1))
        else
            skip "$label (not detected)"
            skipped=$((skipped + 1))
        fi
    }

    # ── Agent list ────────────────────────────────────────────────────────────
    try "Claude Code"      "$HOME/.claude"                    "$HOME/.claude/skills"
    try "Cursor"           "$HOME/.cursor"                    "$HOME/.cursor/skills"
    try "Windsurf"         "$HOME/.codeium/windsurf"          "$HOME/.codeium/windsurf/skills"
    try "Cline"            "$HOME/.cline"                     "$HOME/.cline/skills"
    try "Continue"         "$HOME/.continue"                  "$HOME/.continue/skills"
    try "Roo Code"         "$HOME/.roo"                       "$HOME/.roo/skills"
    try "Kilo Code"        "$HOME/.kilocode"                  "$HOME/.kilocode/skills"
    try "Kiro"             "$HOME/.kiro"                      "$HOME/.kiro/skills"
    try "Augment"          "$HOME/.augment"                   "$HOME/.augment/skills"
    try "GitHub Copilot"   "$HOME/.copilot"                   "$HOME/.copilot/skills"
    try "Gemini CLI"       "gemini"                           "$HOME/.gemini/skills"
    try "Codex"            "codex"                            "$HOME/.codex/skills"
    try "Goose"            "goose"                            "${XDG_CONFIG_HOME:-$HOME/.config}/goose/skills"
    try "OpenCode"         "opencode"                         "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills"

    # ── Summary ───────────────────────────────────────────────────────────────
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ "$installed" -eq 0 ]; then
        warn "No agents detected."
        echo ""
        echo "  Supported: Claude Code, Cursor, Windsurf, Cline, Continue,"
        echo "             Roo Code, Kilo Code, Kiro, Augment, Copilot,"
        echo "             Gemini CLI, Codex, Goose, OpenCode"
    else
        echo -e "  ${GREEN}Installed: $installed${NC}  |  Skipped: $skipped"
        echo ""
        echo "  Canonical: $SKILL_CANONICAL/"
        echo ""
        echo "  To update:   twin-mind install-skills --update"
        echo "  To preview:  twin-mind install-skills --dry-run"
    fi

    echo ""
}

main "$@"
