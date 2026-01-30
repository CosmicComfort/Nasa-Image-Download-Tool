"""
Terminal utilities for cross-platform console operations.
"""

import os
import shutil
import sys
from typing import Tuple


def enable_ansi_on_windows() -> None:
    """Enable ANSI escape sequences on Windows (best-effort)."""
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            new_mode = mode.value | 0x0004
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


def clear_screen() -> None:
    """Clear the terminal screen and move cursor to home position."""
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def hide_cursor() -> None:
    """Hide the terminal cursor."""
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor() -> None:
    """Show the terminal cursor."""
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def move_cursor(row: int, col: int) -> None:
    """Move cursor to specified position (1-indexed)."""
    sys.stdout.write(f"\x1b[{row};{col}H")
    sys.stdout.flush()


def save_cursor() -> None:
    """Save current cursor position."""
    sys.stdout.write("\x1b[s")
    sys.stdout.flush()


def restore_cursor() -> None:
    """Restore saved cursor position."""
    sys.stdout.write("\x1b[u")
    sys.stdout.flush()


def get_terminal_size() -> Tuple[int, int]:
    """
    Get terminal size (columns, lines) with sensible defaults.

    Returns:
        Tuple of (columns, lines) with minimums of (60, 15).
    """
    try:
        size = shutil.get_terminal_size()
        return max(60, size.columns), max(15, size.lines)
    except Exception:
        return 100, 30


def safe_print(text: str = "", end: str = "\n") -> None:
    """
    Safely print text to stdout with proper flushing.

    Handles Unicode encoding errors gracefully on Windows.

    Args:
        text: Text to print
        end: Line ending (default: newline)
    """
    try:
        sys.stdout.write(text + end)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Fallback for Windows consoles that don't support Unicode
        encoded = text.encode(sys.stdout.encoding or 'utf-8', errors='replace')
        sys.stdout.write(encoded.decode(sys.stdout.encoding or 'utf-8') + end)
        sys.stdout.flush()


def center_text(text: str, width: int = None) -> str:
    """
    Center text within terminal width.

    Args:
        text: Text to center
        width: Target width (defaults to terminal width)

    Returns:
        Centered text string
    """
    if width is None:
        width, _ = get_terminal_size()
    return text.center(width)
