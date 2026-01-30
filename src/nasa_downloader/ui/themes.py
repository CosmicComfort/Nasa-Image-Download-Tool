"""
Color themes and styling for NASA Media Downloader.
"""

from dataclasses import dataclass


@dataclass
class ANSIColors:
    """ANSI escape codes for terminal colors."""

    CYAN = "\x1b[36m"
    YELLOW = "\x1b[33m"
    GREEN = "\x1b[32m"
    RED = "\x1b[31m"
    MAGENTA = "\x1b[35m"
    BLUE = "\x1b[34m"
    WHITE = "\x1b[37m"
    BLACK = "\x1b[30m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    UNDERLINE = "\x1b[4m"
    RESET = "\x1b[0m"


class Theme:
    """Theme configuration for the application."""

    # Singleton colors instance
    colors = ANSIColors()

    # Shorthand access
    CYAN = colors.CYAN
    YELLOW = colors.YELLOW
    GREEN = colors.GREEN
    RED = colors.RED
    MAGENTA = colors.MAGENTA
    BLUE = colors.BLUE
    WHITE = colors.WHITE
    BLACK = colors.BLACK
    BOLD = colors.BOLD
    DIM = colors.DIM
    UNDERLINE = colors.UNDERLINE
    RESET = colors.RESET

    @classmethod
    def success(cls, text: str) -> str:
        """Format success message."""
        return f"{cls.GREEN}✓{cls.RESET} {text}"

    @classmethod
    def error(cls, text: str) -> str:
        """Format error message."""
        return f"{cls.RED}✗{cls.RESET} {text}"

    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning message."""
        return f"{cls.YELLOW}⚠{cls.RESET} {text}"

    @classmethod
    def info(cls, text: str) -> str:
        """Format info message."""
        return f"{cls.CYAN}ℹ{cls.RESET} {text}"

    @classmethod
    def header(cls, text: str, width: int = 60) -> str:
        """Format header with decorative borders."""
        border = f"{cls.CYAN}{'═' * width}{cls.RESET}"
        return f"\n{border}\n{cls.BOLD}{cls.CYAN}  {text}{cls.RESET}\n{border}"

    @classmethod
    def subheader(cls, text: str, width: int = 60) -> str:
        """Format subheader with lighter borders."""
        border = f"{cls.CYAN}{'─' * width}{cls.RESET}"
        return f"{border}\n{cls.BOLD}{cls.BLUE}{text}{cls.RESET}\n{border}"

    @classmethod
    def queued_image(cls, title: str) -> str:
        """Format queued image message."""
        return f"{cls.GREEN}✓{cls.RESET} Queued: {title}"

    @classmethod
    def queued_video(cls, title: str) -> str:
        """Format queued video message."""
        return f"{cls.MAGENTA}▶{cls.RESET} Queued: {title}"

    @classmethod
    def mission_complete(cls) -> str:
        """Format mission complete header."""
        return cls.header("MISSION COMPLETE")
