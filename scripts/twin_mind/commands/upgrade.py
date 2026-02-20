"""Upgrade command for twin-mind."""

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from twin_mind.config import get_config
from twin_mind.constants import VERSION
from twin_mind.output import Colors, confirm, error, info, success, supports_color, warning

REPO_URL = "https://raw.githubusercontent.com/pego/twin-mind/main"
RAW_HOST = "raw.githubusercontent.com"
ALLOWED_REPO_PREFIX = "/pego/twin-mind/"

CORE_MODULES = [
    "__init__",
    "constants",
    "output",
    "config",
    "fs",
    "git",
    "memory",
    "memvid_check",
    "index_state",
    "shared_memory",
    "indexing",
    "entity_extractors",
    "js_oxc",
    "entity_graph",
    "auto_init",
    "cli",
]

COMMAND_MODULES = [
    "__init__",
    "init",
    "index",
    "remember",
    "search",
    "ask",
    "recent",
    "stats",
    "status",
    "reset",
    "reindex",
    "prune",
    "context",
    "entities",
    "export",
    "doctor",
    "upgrade",
    "uninstall",
    "install_skills",
]


def _validate_fetch_url(url: str) -> None:
    """Allow only trusted HTTPS URLs from the official raw GitHub host."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed for upgrade downloads")
    if parsed.netloc != RAW_HOST:
        raise ValueError(f"Unexpected host for upgrade download: {parsed.netloc}")
    if not parsed.path.startswith(ALLOWED_REPO_PREFIX):
        raise ValueError(f"Unexpected repository path for upgrade download: {parsed.path}")


def _fetch_url(url: str) -> str:
    """Fetch URL content from the trusted Twin-Mind upstream."""
    _validate_fetch_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "twin-mind-upgrade"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            raise RuntimeError(
                "TLS certificate verification failed. Fix your local trust store and retry."
            ) from e
        raise


def _parse_version(v: str) -> Tuple[int, ...]:
    """Parse version string into comparable tuple."""
    try:
        parts = v.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _download_release_bundle(repo_url: str) -> Dict[str, str]:
    """Download all required files before mutating local installation."""
    required_paths = [
        "scripts/twin-mind.py",
        "SKILL.md",
        "install-skills.sh",
    ]
    required_paths.extend(f"scripts/twin_mind/{module}.py" for module in CORE_MODULES)
    required_paths.extend(f"scripts/twin_mind/commands/{module}.py" for module in COMMAND_MODULES)

    bundle: Dict[str, str] = {}
    for rel_path in required_paths:
        try:
            bundle[rel_path] = _fetch_url(f"{repo_url}/{rel_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to download {rel_path}: {e}") from e
    return bundle


def _install_oxc_parser_runtime(install_dir: Path) -> None:
    """Best-effort install of optional oxc-parser runtime backend."""
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        print(warning("Node.js/npm not found - oxc-parser install skipped (fallback parser active)."))
        return

    package_json = install_dir / "package.json"
    if not package_json.exists():
        package_json.write_text(
            json.dumps({"name": "twin-mind-runtime", "private": True}, indent=2) + "\n",
            encoding="utf-8",
        )

    try:
        completed = subprocess.run(
            [npm, "install", "--silent", "--no-audit", "--no-fund", "--prefix", str(install_dir), "oxc-parser"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(warning(f"oxc-parser install skipped: {exc}"))
        return

    if completed.returncode == 0:
        print(f"   {success('+')} Installed/updated oxc-parser runtime")
        return

    detail = (completed.stderr or completed.stdout or "").strip()
    if detail:
        detail = detail.splitlines()[-1]
        print(warning(f"oxc-parser install skipped: {detail}"))
    else:
        print(warning("oxc-parser install skipped (npm failed)."))


def cmd_upgrade(args: Any) -> None:
    """Check for updates and upgrade twin-mind if a newer version is available."""
    config = get_config()
    if not config["output"]["color"] or not supports_color():
        Colors.disable()

    INSTALL_DIR = Path.home() / ".twin-mind"
    SKILL_DIR = Path.home() / ".agents" / "skills" / "twin-mind"

    print("\nTwin-Mind Upgrade")
    print("=" * 50)

    # Check if installed globally
    if not INSTALL_DIR.exists():
        print(warning("Twin-mind is not installed globally."))
        print("   Run the installer to set up global installation:")
        print(
            "   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash"
        )
        return

    # Get current version
    current_version = VERSION
    version_file = INSTALL_DIR / "version.txt"
    if version_file.exists():
        try:
            current_version = version_file.read_text().strip()
        except OSError:
            current_version = VERSION

    print(f"   Current version: {current_version}")

    # Fetch latest version from GitHub
    print("   Checking for updates...")

    try:
        # Fetch constants.py — the single source of truth for VERSION
        remote_constants = _fetch_url(f"{REPO_URL}/scripts/twin_mind/constants.py")

        # Extract version from constants.py
        version_match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', remote_constants)
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

    current_tuple = _parse_version(current_version)
    latest_tuple = _parse_version(latest_version)

    if current_tuple >= latest_tuple:
        print(f"\n{success('You are already running the latest version!')}")
        return

    print(f"\n   {info('New version available!')}")
    print(f"   {current_version} -> {latest_version}")

    # Check for --check flag (just check, don't upgrade)
    if getattr(args, "check", False):
        print("\n   Run 'twin-mind upgrade' to update.")
        return

    # Confirm upgrade
    if not getattr(args, "force", False):
        if not confirm(f"\n   Upgrade to {latest_version}?"):
            print("   Upgrade cancelled.")
            return

    # Perform upgrade
    print(f"\n   {info('Upgrading...')}")

    current_script = INSTALL_DIR / "twin-mind.py"
    backup_script = INSTALL_DIR / "twin-mind.py.backup"
    package_dir = INSTALL_DIR / "twin_mind"
    commands_dir = package_dir / "commands"
    package_backup = INSTALL_DIR / "twin_mind.backup"

    try:
        # Download everything first to avoid partial upgrades due to network failures.
        bundle = _download_release_bundle(REPO_URL)

        # Backup current script
        if current_script.exists():
            shutil.copy2(current_script, backup_script)
            print(f"   {success('+')} Backed up current version")

        # Backup existing package
        if package_dir.exists():
            if package_backup.exists():
                shutil.rmtree(package_backup)
            shutil.copytree(package_dir, package_backup)
            print(f"   {success('+')} Backed up twin_mind package")

        # Write new entry-point script
        current_script.write_text(bundle["scripts/twin-mind.py"], encoding="utf-8")
        current_script.chmod(0o755)
        print(f"   {success('+')} Updated twin-mind.py")

        # Update twin_mind package atomically from pre-fetched content
        print(f"   {info('Updating twin_mind package...')}")

        # Create directories
        package_dir.mkdir(parents=True, exist_ok=True)
        commands_dir.mkdir(parents=True, exist_ok=True)

        for module in CORE_MODULES:
            rel_path = f"scripts/twin_mind/{module}.py"
            (package_dir / f"{module}.py").write_text(bundle[rel_path], encoding="utf-8")

        for module in COMMAND_MODULES:
            rel_path = f"scripts/twin_mind/commands/{module}.py"
            (commands_dir / f"{module}.py").write_text(bundle[rel_path], encoding="utf-8")

        print(f"   {success('+')} Updated twin_mind package")

        # Update version file
        version_file.write_text(latest_version, encoding="utf-8")
        print(f"   {success('+')} Updated version.txt")

        # Update SKILL.md in canonical location (~/.agents/skills/twin-mind/)
        SKILL_DIR.mkdir(parents=True, exist_ok=True)
        (SKILL_DIR / "SKILL.md").write_text(bundle["SKILL.md"], encoding="utf-8")
        print(f"   {success('+')} Updated SKILL.md")

        # Update install-skills.sh
        skills_sh_path = INSTALL_DIR / "install-skills.sh"
        skills_sh_path.write_text(bundle["install-skills.sh"], encoding="utf-8")
        skills_sh_path.chmod(0o755)
        print(f"   {success('+')} Updated install-skills.sh")

        _install_oxc_parser_runtime(INSTALL_DIR)

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
                print("   Restored from backup.")
            except Exception:
                pass
        if package_backup.exists():
            try:
                if package_dir.exists():
                    shutil.rmtree(package_dir)
                shutil.copytree(package_backup, package_dir)
                print("   Restored twin_mind package from backup.")
            except Exception:
                pass

        print("   Please try reinstalling manually:")
        print(
            "   curl -sSL https://raw.githubusercontent.com/pego/twin-mind/main/install.sh | bash"
        )
