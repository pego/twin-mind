#!/bin/bash
#
# Twin-Mind Installer
# One-command installation for Claude Code integration
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash
#   or
#   ./install.sh (from cloned repo)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.twin-mind"
SKILL_DIR="$HOME/.claude/skills/twin-mind"
REPO_URL="https://raw.githubusercontent.com/pego/twin-mind/main"
MIN_PYTHON_VERSION="3.8"

# Helper functions
info() { echo -e "${BLUE}$1${NC}"; }
success() { echo -e "${GREEN}$1${NC}"; }
warn() { echo -e "${YELLOW}$1${NC}"; }
error() { echo -e "${RED}$1${NC}"; exit 1; }

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get Python command (python3 or python)
get_python_cmd() {
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# Check Python version
check_python_version() {
    local python_cmd=$1
    local version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)

    if [ -z "$version" ]; then
        return 1
    fi

    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)
    local req_major=$(echo $MIN_PYTHON_VERSION | cut -d. -f1)
    local req_minor=$(echo $MIN_PYTHON_VERSION | cut -d. -f2)

    if [ "$major" -gt "$req_major" ] || ([ "$major" -eq "$req_major" ] && [ "$minor" -ge "$req_minor" ]); then
        return 0
    fi
    return 1
}

# Detect shell config file
get_shell_config() {
    local shell_name=$(basename "$SHELL")
    case "$shell_name" in
        zsh)  echo "$HOME/.zshrc" ;;
        bash)
            if [ -f "$HOME/.bash_profile" ]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        *)    echo "$HOME/.profile" ;;
    esac
}

# Check if alias already exists
alias_exists() {
    local config_file=$1
    grep -q "alias twin-mind=" "$config_file" 2>/dev/null
}

# Download file (works with curl or wget)
download_file() {
    local url=$1
    local dest=$2

    if command_exists curl; then
        curl -sSL "$url" -o "$dest"
    elif command_exists wget; then
        wget -q "$url" -O "$dest"
    else
        error "Neither curl nor wget found. Please install one of them."
    fi
}

# Main installation
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Twin-Mind Installer            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""

    # Step 1: Check Python
    info "Checking Python installation..."
    PYTHON_CMD=$(get_python_cmd)

    if [ -z "$PYTHON_CMD" ]; then
        error "Python not found. Please install Python $MIN_PYTHON_VERSION or higher."
    fi

    if ! check_python_version "$PYTHON_CMD"; then
        error "Python $MIN_PYTHON_VERSION+ required. Found: $($PYTHON_CMD --version)"
    fi

    success "  ✓ Found $($PYTHON_CMD --version)"

    # Step 2: Check if already installed
    if [ -d "$INSTALL_DIR" ]; then
        warn "  Twin-mind already installed at $INSTALL_DIR"
        read -p "  Reinstall? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Installation cancelled."
            exit 0
        fi
        rm -rf "$INSTALL_DIR"
    fi

    # Step 3: Create install directory
    info "Creating installation directory..."
    mkdir -p "$INSTALL_DIR"
    success "  ✓ Created $INSTALL_DIR"

    # Step 4: Create virtual environment
    info "Creating isolated Python environment..."
    $PYTHON_CMD -m venv "$INSTALL_DIR/venv"
    success "  ✓ Created virtual environment"

    # Step 5: Install memvid-sdk
    info "Installing memvid-sdk..."
    "$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install --quiet memvid-sdk
    success "  ✓ Installed memvid-sdk"

    # Step 6: Install twin-mind.py and twin_mind package
    info "Installing twin-mind..."

    # Check if running from repo (local install) or via curl (remote install)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/scripts/twin-mind.py" ]; then
        # Local install from repo
        cp "$SCRIPT_DIR/scripts/twin-mind.py" "$INSTALL_DIR/twin-mind.py"
        # Copy package directory
        if [ -d "$SCRIPT_DIR/scripts/twin_mind" ]; then
            cp -r "$SCRIPT_DIR/scripts/twin_mind" "$INSTALL_DIR/twin_mind"
        fi
    else
        # Remote install via curl - download main script
        download_file "$REPO_URL/scripts/twin-mind.py" "$INSTALL_DIR/twin-mind.py"

        # Download package files
        info "  Downloading twin_mind package..."
        mkdir -p "$INSTALL_DIR/twin_mind/commands"

        # Core modules
        for module in __init__ constants output config fs git memory memvid_check index_state shared_memory indexing auto_init cli; do
            download_file "$REPO_URL/scripts/twin_mind/${module}.py" "$INSTALL_DIR/twin_mind/${module}.py"
        done

        # Command modules
        download_file "$REPO_URL/scripts/twin_mind/commands/__init__.py" "$INSTALL_DIR/twin_mind/commands/__init__.py"
        for cmd in init index remember search ask recent stats status reset reindex prune context export doctor upgrade uninstall; do
            download_file "$REPO_URL/scripts/twin_mind/commands/${cmd}.py" "$INSTALL_DIR/twin_mind/commands/${cmd}.py"
        done
    fi
    chmod +x "$INSTALL_DIR/twin-mind.py"
    success "  ✓ Installed twin-mind.py"
    success "  ✓ Installed twin_mind package"

    # Step 7: Create version file (read from constants.py — single source of truth)
    VERSION=$(grep -m1 'VERSION' "$INSTALL_DIR/twin_mind/constants.py" | sed "s/.*VERSION *= *['\"]\\([^'\"]*\\)['\"].*/\\1/")
    echo "$VERSION" > "$INSTALL_DIR/version.txt"

    # Step 8: Download SKILL.md + install-skills.sh to canonical location,
    #         then symlink into all detected agents
    info "Installing skill for detected agents..."

    # Save SKILL.md to ~/.twin-mind/SKILL.md (source of truth for symlinks)
    if [ -f "$SCRIPT_DIR/SKILL.md" ]; then
        cp "$SCRIPT_DIR/SKILL.md" "$INSTALL_DIR/SKILL.md"
    else
        download_file "$REPO_URL/SKILL.md" "$INSTALL_DIR/SKILL.md"
    fi

    # Save install-skills.sh to ~/.twin-mind/ so `twin-mind install-skills` can use it
    if [ -f "$SCRIPT_DIR/install-skills.sh" ]; then
        cp "$SCRIPT_DIR/install-skills.sh" "$INSTALL_DIR/install-skills.sh"
    else
        download_file "$REPO_URL/install-skills.sh" "$INSTALL_DIR/install-skills.sh"
    fi
    chmod +x "$INSTALL_DIR/install-skills.sh"

    # Run the skills installer
    bash "$INSTALL_DIR/install-skills.sh"

    # Step 9: Add shell alias
    info "Configuring shell alias..."
    SHELL_CONFIG=$(get_shell_config)
    ALIAS_LINE="alias twin-mind=\"$INSTALL_DIR/venv/bin/python $INSTALL_DIR/twin-mind.py\""

    if alias_exists "$SHELL_CONFIG"; then
        # Update existing alias
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|alias twin-mind=.*|$ALIAS_LINE|" "$SHELL_CONFIG"
        else
            sed -i "s|alias twin-mind=.*|$ALIAS_LINE|" "$SHELL_CONFIG"
        fi
        success "  ✓ Updated alias in $SHELL_CONFIG"
    else
        # Add new alias
        echo "" >> "$SHELL_CONFIG"
        echo "# Twin-Mind - AI coding assistant memory" >> "$SHELL_CONFIG"
        echo "$ALIAS_LINE" >> "$SHELL_CONFIG"
        success "  ✓ Added alias to $SHELL_CONFIG"
    fi

    # Done!
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     Installation Complete!             ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "  To start using twin-mind, either:"
    echo ""
    echo "    1. Restart your terminal, or"
    echo "    2. Run: source $SHELL_CONFIG"
    echo ""
    echo "  Then in any project directory:"
    echo ""
    echo "    twin-mind search \"your query\"    # Search code"
    echo "    twin-mind remember \"insight\"     # Save a memory"
    echo "    twin-mind status                  # Check status"
    echo ""
    echo "  First command in a new project auto-initializes."
    echo ""
}

# Run main
main "$@"
