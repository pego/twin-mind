"""Memvid availability check for twin-mind."""

import sys
from types import ModuleType
from typing import Optional

try:
    import memvid_sdk

    MEMVID_AVAILABLE: bool = True
    MEMVID_IMPORT_ERROR: Optional[str] = None
except ImportError as e:
    MEMVID_AVAILABLE = False
    MEMVID_IMPORT_ERROR = str(e)
    memvid_sdk = None  # type: ignore[assignment]


def check_memvid() -> None:
    """Check if memvid is available, exit if not."""
    if not MEMVID_AVAILABLE:
        print("memvid-sdk not installed or import failed.")
        print(f"   Python: {sys.executable}")
        print(f"   Error: {MEMVID_IMPORT_ERROR}")
        print("   Run: pip install memvid-sdk --break-system-packages")
        sys.exit(1)


def get_memvid_sdk() -> Optional[ModuleType]:
    """Get the memvid_sdk module (for use after check_memvid)."""
    return memvid_sdk
