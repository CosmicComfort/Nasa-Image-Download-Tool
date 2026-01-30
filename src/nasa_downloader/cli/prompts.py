"""
Interactive prompts and menus for the CLI.
"""

import sys
from typing import List, Optional

from ..core.config import QUALITY_SUFFIXES
from ..ui.themes import Theme
from ..ui.terminal import safe_print


def themed_input(prompt: str, default: str = "") -> str:
    """
    Display themed input prompt with optional default value.

    Args:
        prompt: Prompt text to display
        default: Default value if user enters nothing

    Returns:
        User input or default value
    """
    hint = f" [{default}]" if default else ""
    sys.stdout.write(
        f"\n{Theme.CYAN}►{Theme.RESET} {prompt}{hint}\n{Theme.YELLOW}▸{Theme.RESET} "
    )
    sys.stdout.flush()

    try:
        value = input().strip()
    except EOFError:
        value = ""

    return value if value else default


def parse_quality_input(choice: str) -> List[str]:
    """
    Parse quality selection from user input.

    Accepts:
    - Numbers 1-5 (1=small, 2=medium, 3=large, 4=orig, 5=all)
    - Comma-separated values
    - Quality names directly

    Args:
        choice: User input string

    Returns:
        List of quality names
    """
    mapping = {
        "1": "small",
        "2": "medium",
        "3": "large",
        "4": "orig",
        "5": "all",
    }

    choice = choice.strip().lower()

    # Handle "all" option
    if choice in ("5", "all"):
        return ["small", "medium", "large", "orig"]

    # Parse comma-separated values
    parts = [p.strip() for p in choice.split(",") if p.strip()]
    result = []

    for part in parts:
        if part in mapping:
            quality = mapping[part]
            if quality != "all":
                result.append(quality)
        elif part in QUALITY_SUFFIXES:
            result.append(part)
        else:
            # Default to orig for unknown values
            result.append("orig")

    # Remove duplicates while preserving order
    seen = set()
    final = []
    for quality in result:
        if quality not in seen:
            final.append(quality)
            seen.add(quality)

    return final or ["orig"]


def show_menu(title: str, options: List[str], default: int = 1) -> int:
    """
    Display a menu and get user selection.

    Args:
        title: Menu title
        options: List of option strings
        default: Default option number (1-indexed)

    Returns:
        Selected option number (1-indexed)
    """
    safe_print(f"\n{Theme.BOLD}{Theme.BLUE}{title}{Theme.RESET}")
    safe_print(f"{Theme.CYAN}{'─' * 60}{Theme.RESET}")

    for i, option in enumerate(options, 1):
        marker = "●" if i == default else "○"
        safe_print(f"  {Theme.YELLOW}{marker}{Theme.RESET} {i}. {option}")

    safe_print(f"{Theme.CYAN}{'─' * 60}{Theme.RESET}")

    choice = themed_input(f"Select option (1-{len(options)})", str(default))

    try:
        num = int(choice)
        return num if 1 <= num <= len(options) else default
    except ValueError:
        return default


def show_quality_menu() -> List[str]:
    """
    Show quality selection menu.

    Returns:
        List of selected quality levels
    """
    options = [
        "Small (Low resolution, faster downloads)",
        "Medium (Balanced quality and size)",
        "Large (High resolution)",
        "Original (Best quality, largest files)",
        "All qualities (Download all available)",
    ]
    choice = show_menu("SELECT IMAGE/VIDEO QUALITY", options, default=4)
    return parse_quality_input(str(choice))


def show_media_type_menu() -> tuple:
    """
    Show media type selection menu.

    Returns:
        Tuple of (download_images, download_videos)
    """
    options = [
        "Images only",
        "Videos only",
        "Both images and videos",
    ]
    choice = show_menu("SELECT MEDIA TYPES TO DOWNLOAD", options, default=1)

    download_images = choice in (1, 3)
    download_videos = choice in (2, 3)

    return download_images, download_videos


def show_metadata_menu() -> bool:
    """
    Show metadata options menu.

    Returns:
        True if metadata should be downloaded
    """
    options = [
        "Download media files only",
        "Download media + metadata (JSON + TXT)",
    ]
    choice = show_menu("METADATA OPTIONS", options, default=2)
    return choice == 2


def show_limit_menu() -> Optional[int]:
    """
    Show download limit menu.

    Returns:
        Maximum items to download, or None for unlimited
    """
    options = [
        "Download all available items",
        "Specify maximum number",
    ]
    choice = show_menu("DOWNLOAD LIMIT", options, default=1)

    if choice == 2:
        try:
            num = int(themed_input("Maximum number of items", "100"))
            return num if num > 0 else None
        except ValueError:
            return None

    return None


def confirm_mission(
    query: str,
    output_path: str,
    qualities: List[str],
    download_images: bool,
    download_videos: bool,
    download_metadata: bool,
    max_items: Optional[int],
) -> bool:
    """
    Display mission parameters and wait for confirmation.

    Args:
        query: Search query
        output_path: Output directory path
        qualities: List of quality levels
        download_images: Whether to download images
        download_videos: Whether to download videos
        download_metadata: Whether to save metadata
        max_items: Maximum items limit

    Returns:
        True if user confirms, False otherwise
    """
    safe_print(f"\n{Theme.BOLD}{Theme.GREEN}MISSION PARAMETERS CONFIRMED{Theme.RESET}")
    safe_print(f"{Theme.CYAN}{'─' * 60}{Theme.RESET}")
    safe_print(f"  Query: {Theme.YELLOW}{query}{Theme.RESET}")
    safe_print(f"  Output: {Theme.YELLOW}{output_path}{Theme.RESET}")
    safe_print(f"  Qualities: {Theme.YELLOW}{', '.join(qualities)}{Theme.RESET}")
    safe_print(f"  Images: {Theme.YELLOW}{download_images}{Theme.RESET}")
    safe_print(f"  Videos: {Theme.YELLOW}{download_videos}{Theme.RESET}")
    safe_print(f"  Metadata: {Theme.YELLOW}{download_metadata}{Theme.RESET}")
    safe_print(f"  Limit: {Theme.YELLOW}{max_items or 'None'}{Theme.RESET}")
    safe_print(f"{Theme.CYAN}{'─' * 60}{Theme.RESET}\n")

    themed_input("Press Enter to launch mission...", "")
    return True
