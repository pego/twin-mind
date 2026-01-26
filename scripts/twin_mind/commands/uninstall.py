"""Uninstall command for twin-mind."""

import shutil
from pathlib import Path

from twin_mind.output import success, error, warning, confirm


def cmd_uninstall(args):
    """Uninstall twin-mind from the system."""
    install_dir = Path.home() / '.twin-mind'
    skill_dir = Path.home() / '.claude' / 'skills' / 'twin-mind'

    print(f"\nTwin-Mind Uninstaller")
    print("=" * 40)

    items_to_remove = []
    if install_dir.exists():
        items_to_remove.append(('Installation directory', install_dir))
    if skill_dir.exists():
        items_to_remove.append(('Skill directory', skill_dir))

    if not items_to_remove:
        print("Nothing to uninstall - twin-mind is not installed globally.")
        print("\nTo remove from current project: rm -rf .claude/")
        return

    print("\nWill remove:")
    for name, path in items_to_remove:
        print(f"  - {name}: {path}")

    # Check for alias in shell config
    shell_configs = [
        Path.home() / '.zshrc',
        Path.home() / '.bashrc',
        Path.home() / '.bash_profile',
        Path.home() / '.profile'
    ]

    alias_found_in = []
    for config in shell_configs:
        if config.exists():
            try:
                content = config.read_text()
                if 'alias twin-mind=' in content:
                    alias_found_in.append(config)
            except Exception:
                pass

    if alias_found_in:
        print(f"\nWill remove alias from:")
        for config in alias_found_in:
            print(f"  - {config}")

    if not getattr(args, 'force', False):
        if not confirm("\nProceed with uninstall?"):
            print("Cancelled.")
            return

    # Remove directories
    for name, path in items_to_remove:
        try:
            shutil.rmtree(path)
            print(f"  {success('+')} Removed {path}")
        except Exception as e:
            print(f"  {error(f'Failed to remove {path}: {e}')}")

    # Remove alias from shell configs
    for config in alias_found_in:
        try:
            content = config.read_text()
            lines = content.split('\n')
            new_lines = []
            skip_next = False
            for line in lines:
                # Skip the alias line and the comment before it
                if 'Twin-Mind - AI coding assistant' in line:
                    skip_next = True
                    continue
                if skip_next and 'alias twin-mind=' in line:
                    skip_next = False
                    continue
                if 'alias twin-mind=' in line:
                    continue
                new_lines.append(line)
            config.write_text('\n'.join(new_lines))
            print(f"  {success('+')} Removed alias from {config}")
        except Exception as e:
            print(f"  {warning(f'Could not update {config}: {e}')}")

    print(f"\n{success('Twin-mind uninstalled.')}")
    print("\nNote: Project-specific .claude/ directories are preserved.")
    print("To remove them: rm -rf /path/to/project/.claude/")
