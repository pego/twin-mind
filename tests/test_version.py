"""Ensure VERSION stays in sync across all files that declare it."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
ENTRY_POINT = REPO_ROOT / "scripts" / "twin-mind.py"


def _extract_literal_version(path: Path) -> str:
    """Return the first VERSION = '...' literal found in a file."""
    text = path.read_text()
    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    assert m, f"No literal VERSION = '...' found in {path}"
    return m.group(1)


class TestVersionConsistency:
    def test_entry_point_matches_constants(self) -> None:
        """scripts/twin-mind.py literal VERSION must match twin_mind/constants.py."""
        from twin_mind.constants import VERSION as canonical

        literal = _extract_literal_version(ENTRY_POINT)
        assert literal == canonical, (
            f"scripts/twin-mind.py has VERSION = '{literal}' but "
            f"twin_mind/constants.py has VERSION = '{canonical}'. "
            "Update the literal in scripts/twin-mind.py to match."
        )
