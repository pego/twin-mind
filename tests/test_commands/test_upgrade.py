"""Tests for the upgrade command."""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest


class MockArgs:
    """Mock args object for command functions."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def _build_bundle() -> Dict[str, str]:
    """Build a complete fake release bundle for upgrade tests."""
    from twin_mind.commands.upgrade import COMMAND_MODULES, CORE_MODULES

    bundle = {
        "scripts/twin-mind.py": "#!/usr/bin/env python3\nprint('new twin-mind')\n",
        "SKILL.md": "# Twin-Mind Skill\n",
        "install-skills.sh": "#!/bin/bash\necho install skills\n",
    }
    for module in CORE_MODULES:
        bundle[f"scripts/twin_mind/{module}.py"] = f"# core:{module}\n"
    for module in COMMAND_MODULES:
        bundle[f"scripts/twin_mind/commands/{module}.py"] = f"# cmd:{module}\n"
    return bundle


class TestUpgradeHelpers:
    """Tests for upgrade helper functions."""

    def test_validate_fetch_url_rejects_untrusted_targets(self) -> None:
        """Only the expected upstream raw GitHub URL should be accepted."""
        from twin_mind.commands.upgrade import _validate_fetch_url

        with pytest.raises(ValueError):
            _validate_fetch_url("http://raw.githubusercontent.com/pego/twin-mind/main/SKILL.md")
        with pytest.raises(ValueError):
            _validate_fetch_url("https://example.com/pego/twin-mind/main/SKILL.md")
        with pytest.raises(ValueError):
            _validate_fetch_url("https://raw.githubusercontent.com/other/repo/main/SKILL.md")


class TestCmdUpgrade:
    """Tests for cmd_upgrade."""

    def test_upgrade_check_mode_does_not_download_bundle(self, tmp_path: Any, capsys: Any) -> None:
        """`--check` should report availability without mutating installation."""
        install_dir = tmp_path / ".twin-mind"
        install_dir.mkdir(parents=True)
        version_file = install_dir / "version.txt"
        version_file.write_text("1.8.1")

        with patch("twin_mind.commands.upgrade.Path.home", return_value=tmp_path), patch(
            "twin_mind.commands.upgrade.get_config", return_value={"output": {"color": False}}
        ), patch("twin_mind.commands.upgrade.supports_color", return_value=False), patch(
            "twin_mind.commands.upgrade._fetch_url", return_value='VERSION = "1.8.2"'
        ), patch(
            "twin_mind.commands.upgrade._download_release_bundle"
        ) as mock_download_bundle, patch(
            "twin_mind.commands.upgrade._install_oxc_parser_runtime"
        ):
            from twin_mind.commands.upgrade import cmd_upgrade

            cmd_upgrade(MockArgs(check=True, force=False))

        captured = capsys.readouterr()
        assert "New version available" in captured.out
        assert "Run 'twin-mind upgrade' to update." in captured.out
        assert version_file.read_text() == "1.8.1"
        mock_download_bundle.assert_not_called()

    def test_upgrade_success_writes_all_artifacts(self, tmp_path: Any, capsys: Any) -> None:
        """Successful upgrade should write script/package/version/skill artifacts."""
        install_dir = tmp_path / ".twin-mind"
        package_dir = install_dir / "twin_mind"
        commands_dir = package_dir / "commands"
        install_dir.mkdir(parents=True)
        commands_dir.mkdir(parents=True)

        (install_dir / "twin-mind.py").write_text("print('old')\n")
        (package_dir / "__init__.py").write_text("# old package\n")
        (commands_dir / "__init__.py").write_text("# old commands\n")
        (install_dir / "version.txt").write_text("1.8.1")

        bundle = _build_bundle()

        with patch("twin_mind.commands.upgrade.Path.home", return_value=tmp_path), patch(
            "twin_mind.commands.upgrade.get_config", return_value={"output": {"color": False}}
        ), patch("twin_mind.commands.upgrade.supports_color", return_value=False), patch(
            "twin_mind.commands.upgrade._fetch_url", return_value='VERSION = "1.8.2"'
        ), patch(
            "twin_mind.commands.upgrade._download_release_bundle", return_value=bundle
        ), patch(
            "twin_mind.commands.upgrade._install_oxc_parser_runtime"
        ):
            from twin_mind.commands.upgrade import cmd_upgrade

            cmd_upgrade(MockArgs(check=False, force=True))

        captured = capsys.readouterr()
        assert "Upgrade complete!" in captured.out
        assert (install_dir / "version.txt").read_text() == "1.8.2"
        assert (install_dir / "twin-mind.py").read_text() == bundle["scripts/twin-mind.py"]
        assert (package_dir / "constants.py").read_text() == bundle["scripts/twin_mind/constants.py"]
        assert (
            commands_dir / "search.py"
        ).read_text() == bundle["scripts/twin_mind/commands/search.py"]
        assert (tmp_path / ".agents" / "skills" / "twin-mind" / "SKILL.md").exists()
        assert (install_dir / "install-skills.sh").exists()

    def test_upgrade_rolls_back_script_and_package_on_write_failure(
        self, tmp_path: Any, capsys: Any, monkeypatch: Any
    ) -> None:
        """If writes fail mid-upgrade, script and package should be restored from backups."""
        install_dir = tmp_path / ".twin-mind"
        package_dir = install_dir / "twin_mind"
        commands_dir = package_dir / "commands"
        install_dir.mkdir(parents=True)
        commands_dir.mkdir(parents=True)

        old_script = "print('old script')\n"
        (install_dir / "twin-mind.py").write_text(old_script)
        (package_dir / "marker.txt").write_text("keep-me\n")
        (commands_dir / "__init__.py").write_text("# old commands\n")
        (install_dir / "version.txt").write_text("1.8.1")

        bundle = _build_bundle()
        original_write_text = Path.write_text

        def flaky_write_text(path_obj: Path, content: str, *args: Any, **kwargs: Any) -> int:
            if path_obj.name == "search.py" and path_obj.parent.name == "commands":
                raise OSError("disk full")
            return original_write_text(path_obj, content, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", flaky_write_text)

        with patch("twin_mind.commands.upgrade.Path.home", return_value=tmp_path), patch(
            "twin_mind.commands.upgrade.get_config", return_value={"output": {"color": False}}
        ), patch("twin_mind.commands.upgrade.supports_color", return_value=False), patch(
            "twin_mind.commands.upgrade._fetch_url", return_value='VERSION = "1.8.2"'
        ), patch(
            "twin_mind.commands.upgrade._download_release_bundle", return_value=bundle
        ), patch(
            "twin_mind.commands.upgrade._install_oxc_parser_runtime"
        ):
            from twin_mind.commands.upgrade import cmd_upgrade

            cmd_upgrade(MockArgs(check=False, force=True))

        captured = capsys.readouterr()
        assert "Upgrade failed" in captured.out
        assert "Restored from backup." in captured.out
        assert "Restored twin_mind package from backup." in captured.out
        assert (install_dir / "twin-mind.py").read_text() == old_script
        assert (package_dir / "marker.txt").read_text() == "keep-me\n"
