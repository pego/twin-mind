#!/bin/bash
#
# Twin-Mind Skills Installer
# Symlinks the twin-mind skill into every detected AI coding agent/IDE.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install-skills.sh | bash
#   ./install-skills.sh            # install for all detected agents
#   ./install-skills.sh --dry-run  # preview without making changes
#   ./install-skills.sh --update   # refresh SKILL.md from GitHub, then reinstall
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
# Canonical source — downloaded once, symlinked everywhere
SKILL_SOURCE="$HOME/.twin-mind/SKILL.md"

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
# Returns 0 if the agent is present (config dir exists OR binary in PATH)
detected() {
    local check="$1"
    [ -d "$check" ] || command -v "$check" >/dev/null 2>&1
}

# ── Install for one agent ─────────────────────────────────────────────────────
install_skill() {
    local label="$1"
    local skills_dir="$2"
    local target="$skills_dir/$SKILL_NAME/SKILL.md"

    if $DRY_RUN; then
        echo -e "  ${BLUE}[dry-run]${NC} $label → $target"
        return
    fi

    mkdir -p "$skills_dir/$SKILL_NAME"

    # Remove stale file or broken symlink
    [ -e "$target" ] || [ -L "$target" ] && rm -f "$target"

    ln -s "$SKILL_SOURCE" "$target"
    success "$label"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}Twin-Mind — Skills Installer${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    $DRY_RUN && warn "Dry-run mode — no changes will be made" && echo ""

    # ── Ensure source SKILL.md exists ─────────────────────────────────────────
    if ! $DRY_RUN && { $UPDATE || [ ! -f "$SKILL_SOURCE" ]; }; then
        info "Downloading SKILL.md from GitHub..."
        mkdir -p "$(dirname "$SKILL_SOURCE")"
        download "$REPO_URL/SKILL.md" "$SKILL_SOURCE"
        success "SKILL.md saved to $SKILL_SOURCE"
        echo ""
    fi

    # ── Detect and install ────────────────────────────────────────────────────
    info "Detecting installed agents..."
    echo ""

    installed=0
    skipped=0

    # Helper: try to install, count result
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
    # Format: try "Label" "detection (dir or binary)" "global skills dir"

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
        echo "  Install an AI coding tool and re-run:"
        echo "    bash install-skills.sh"
        echo ""
        echo "  Supported: Claude Code, Cursor, Windsurf, Cline, Continue,"
        echo "             Roo Code, Kilo Code, Kiro, Augment, Copilot,"
        echo "             Gemini CLI, Codex, Goose, OpenCode"
    else
        echo -e "  ${GREEN}Installed: $installed${NC}  |  Skipped: $skipped"
        echo ""
        echo "  Skill source: $SKILL_SOURCE"
        echo ""
        echo "  To update the skill:  bash install-skills.sh --update"
        echo "  To preview changes:   bash install-skills.sh --dry-run"
    fi

    echo ""
}

main "$@"
