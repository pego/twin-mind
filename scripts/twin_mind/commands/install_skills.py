"""Install-skills command for twin-mind."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from twin_mind.output import error, info, success, warning
from twin_mind.commands.upgrade import _fetch_url

REPO_URL = "https://raw.githubusercontent.com/pego/twin-mind/main"
INSTALL_DIR = Path.home() / ".twin-mind"


def cmd_install_skills(args: Any) -> None:
    """Symlink the twin-mind skill into all detected AI coding agents."""

    # Build flags to forward to the shell script
    flags = []
    if getattr(args, "dry_run", False):
        flags.append("--dry-run")
    if getattr(args, "update", False):
        flags.append("--update")

    # Prefer the locally installed copy so it matches the running version
    local_script = INSTALL_DIR / "install-skills.sh"

    if local_script.exists():
        script_path = str(local_script)
    else:
        # Download from GitHub into a temp file
        print(info("Downloading install-skills.sh from GitHub..."))
        try:
            content = _fetch_url(f"{REPO_URL}/install-skills.sh")
        except Exception as e:
            print(error(f"Failed to fetch install-skills.sh: {e}"))
            sys.exit(1)

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
        tmp.write(content)
        tmp.close()
        os.chmod(tmp.name, 0o755)
        script_path = tmp.name

    try:
        result = subprocess.run(["bash", script_path] + flags)
        sys.exit(result.returncode)
    finally:
        # Clean up temp file if we created one
        if script_path != str(local_script):
            try:
                os.unlink(script_path)
            except OSError:
                pass
