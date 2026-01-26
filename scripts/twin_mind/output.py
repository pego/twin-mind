"""Output helpers for twin-mind."""

import sys
import os

from twin_mind.constants import VERSION


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    BOLD = "\033[1m"

    _enabled = True

    @classmethod
    def disable(cls):
        cls.RESET = cls.RED = cls.GREEN = ""
        cls.YELLOW = cls.BLUE = cls.BOLD = ""
        cls._enabled = False

    @classmethod
    def is_enabled(cls):
        return cls._enabled


def supports_color() -> bool:
    """Check if terminal supports color output."""
    if os.environ.get('NO_COLOR'):
        return False
    if not hasattr(sys.stdout, 'isatty'):
        return False
    return sys.stdout.isatty()


def color(text: str, color_code: str) -> str:
    """Wrap text in color code."""
    if not Colors._enabled:
        return text
    return f"{color_code}{text}{Colors.RESET}"


def success(msg: str) -> str:
    return color(msg, Colors.GREEN)


def warning(msg: str) -> str:
    return color(msg, Colors.YELLOW)


def error(msg: str) -> str:
    return color(msg, Colors.RED)


def info(msg: str) -> str:
    return color(msg, Colors.BLUE)


class ProgressBar:
    """Simple progress bar for terminal."""

    def __init__(self, total: int, width: int = 30, prefix: str = ""):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self._is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    def update(self, n: int = 1):
        self.current += n
        if self._is_tty:
            self._render()

    def _render(self):
        pct = self.current / self.total if self.total > 0 else 1
        filled = int(self.width * pct)
        bar = '=' * filled + '>' + ' ' * (self.width - filled - 1)
        line = f"\r{self.prefix}[{bar}] {self.current}/{self.total} ({pct*100:.0f}%)"
        sys.stdout.write(line)
        sys.stdout.flush()

    def finish(self):
        if self._is_tty:
            sys.stdout.write('\n')
            sys.stdout.flush()


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable size."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024*1024):.2f} MB"


def confirm(message: str) -> bool:
    """Ask user for confirmation."""
    response = input(f"{message} [y/N]: ").strip().lower()
    return response == 'y'


def print_banner():
    """Print ASCII art banner."""
    banner = r"""
  ______         _          __  __ _           _
 |__  __|       (_)        |  \/  (_)         | |
    | |_      __ _ _ __    | \  / |_ _ __   __| |
    | \ \ /\ / / | '_ \   | |\/| | | '_ \ / _` |
    | |\ V  V /| | | | |  | |  | | | | | | (_| |
    |_| \_/\_/ |_|_| |_|  |_|  |_|_|_| |_|\__,_|

    Dual Memory for AI Coding Agents v{version}
    """
    print(banner.format(version=VERSION))
