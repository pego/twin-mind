"""Upgrade command for twin-mind."""

import re
import shutil
import ssl
import urllib.request
import urllib.error
from pathlib import Path

from twin_mind.config import get_config
from twin_mind.constants import VERSION
from twin_mind.output import Colors, supports_color, success, warning, error, info, confirm


def _fetch_url(url: str) -> str:
    """Fetch URL content with SSL fallback for macOS certificate issues."""
    req = urllib.request.Request(url, headers={'User-Agent': 'twin-mind-upgrade'})

    try:
        # Try with default SSL context first
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e):
            # Fallback: create unverified SSL context (common macOS issue)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                return response.read().decode('utf-8')
        raise


def cmd_upgrade(args):
    """Check for updates and upgrade twin-mind if a newer version is available."""
    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    REPO_URL = "https://raw.githubusercontent.com/pego/twin-mind/main"
    INSTALL_DIR = Path.home() / ".twin-mind"
    SKILL_DIR = Path.home() / ".claude" / "skills" / "twin-mind"

    print(f"\nTwin-Mind Upgrade")
    print("=" * 50)

    # Check if installed globally
    if not INSTALL_DIR.exists():
        print(warning("Twin-mind is not installed globally."))
        print("   Run the installer to set up global installation:")
        print("   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash")
        return

    # Get current version
    current_version = VERSION
    version_file = INSTALL_DIR / "version.txt"
    if version_file.exists():
        try:
            current_version = version_file.read_text().strip()
        except Exception:
            pass

    print(f"   Current version: {current_version}")

    # Fetch latest version from GitHub
    print(f"   Checking for updates...")

    try:
        # Fetch the script to get version
        remote_script = _fetch_url(f"{REPO_URL}/scripts/twin-mind.py")

        # Extract version from the script
        version_match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', remote_script)
        if not version_match:
            print(error("Could not determine latest version"))
            return

        latest_version = version_match.group(1)
        print(f"   Latest version:  {latest_version}")

    except urllib.error.URLError as e:
        print(error(f"Failed to check for updates: {e}"))
        print("   Check your internet connection and try again.")
        return
    except Exception as e:
        print(error(f"Error checking for updates: {e}"))
        return

    # Compare versions
    def parse_version(v: str) -> tuple:
        """Parse version string into comparable tuple."""
        try:
            parts = v.split('.')
            return tuple(int(p) for p in parts)
        except (ValueError, AttributeError):
            return (0, 0, 0)

    current_tuple = parse_version(current_version)
    latest_tuple = parse_version(latest_version)

    if current_tuple >= latest_tuple:
        print(f"\n{success('You are already running the latest version!')}")
        return

    print(f"\n   {info('New version available!')}")
    print(f"   {current_version} -> {latest_version}")

    # Check for --check flag (just check, don't upgrade)
    if getattr(args, 'check', False):
        print(f"\n   Run 'twin-mind upgrade' to update.")
        return

    # Confirm upgrade
    if not getattr(args, 'force', False):
        if not confirm(f"\n   Upgrade to {latest_version}?"):
            print("   Upgrade cancelled.")
            return

    # Perform upgrade
    print(f"\n   {info('Upgrading...')}")

    try:
        # Backup current script
        current_script = INSTALL_DIR / "twin-mind.py"
        backup_script = INSTALL_DIR / "twin-mind.py.backup"
        if current_script.exists():
            shutil.copy2(current_script, backup_script)
            print(f"   {success('+')} Backed up current version")

        # Write new script
        current_script.write_text(remote_script, encoding='utf-8')
        current_script.chmod(0o755)
        print(f"   {success('+')} Updated twin-mind.py")

        # Update twin_mind package
        print(f"   {info('Updating twin_mind package...')}")
        package_dir = INSTALL_DIR / "twin_mind"
        commands_dir = package_dir / "commands"

        # Backup existing package
        package_backup = INSTALL_DIR / "twin_mind.backup"
        if package_dir.exists():
            if package_backup.exists():
                shutil.rmtree(package_backup)
            shutil.copytree(package_dir, package_backup)

        # Create directories
        package_dir.mkdir(parents=True, exist_ok=True)
        commands_dir.mkdir(parents=True, exist_ok=True)

        # Download core modules
        core_modules = ['__init__', 'constants', 'output', 'config', 'fs', 'git',
                        'memory', 'memvid_check', 'index_state', 'shared_memory',
                        'indexing', 'auto_init', 'cli']
        for module in core_modules:
            try:
                content = _fetch_url(f"{REPO_URL}/scripts/twin_mind/{module}.py")
                (package_dir / f"{module}.py").write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"   {warning(f'Failed to update {module}.py: {e}')}")

        # Download command modules
        cmd_modules = ['__init__', 'init', 'index', 'remember', 'search', 'ask',
                       'recent', 'stats', 'status', 'reset', 'reindex', 'prune',
                       'context', 'export', 'doctor', 'upgrade', 'uninstall']
        for module in cmd_modules:
            try:
                content = _fetch_url(f"{REPO_URL}/scripts/twin_mind/commands/{module}.py")
                (commands_dir / f"{module}.py").write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"   {warning(f'Failed to update commands/{module}.py: {e}')}")

        print(f"   {success('+')} Updated twin_mind package")

        # Update version file
        version_file.write_text(latest_version)
        print(f"   {success('+')} Updated version.txt")

        # Update SKILL.md
        try:
            skill_content = _fetch_url(f"{REPO_URL}/SKILL.md")
            SKILL_DIR.mkdir(parents=True, exist_ok=True)
            (SKILL_DIR / "SKILL.md").write_text(skill_content, encoding='utf-8')
            print(f"   {success('+')} Updated SKILL.md")
        except Exception as e:
            print(f"   {warning(f'Could not update SKILL.md: {e}')}")

        print(f"\n{success('Upgrade complete!')}")
        print(f"   Now running version {latest_version}")

        # Show if there's a backup
        if backup_script.exists():
            print(f"\n   Backup saved to: {backup_script}")
            print(f"   To rollback: cp {backup_script} {current_script}")

    except Exception as e:
        print(error(f"Upgrade failed: {e}"))

        # Try to restore backup
        if backup_script.exists():
            try:
                shutil.copy2(backup_script, current_script)
                print(f"   Restored from backup.")
            except Exception:
                pass

        print(f"   Please try reinstalling manually:")
        print(f"   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash")
