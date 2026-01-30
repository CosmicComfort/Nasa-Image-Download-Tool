"""
Click-based CLI application for NASA Media Downloader.
"""

import signal
import sys
import time
from pathlib import Path
from typing import Optional

import click

from ..core.config import (
    DEFAULT_SUBDIR,
    DEFAULT_WORKERS,
    MAX_WORKERS,
    MIN_WORKERS,
)
from ..downloader.engine import crawl_nasa_media
from ..ui.terminal import clear_screen, safe_print
from ..ui.themes import Theme
from ..ui.starfield import EnhancedStarfield
from ..ui.intro import SpaceIntro
from .prompts import (
    themed_input,
    parse_quality_input,
    show_quality_menu,
    show_media_type_menu,
    show_metadata_menu,
    show_limit_menu,
    confirm_mission,
)


# Global starfield instance for cleanup
_starfield: Optional[EnhancedStarfield] = None


def signal_handler(sig, frame):
    """Handle interrupt signals gracefully."""
    global _starfield
    if _starfield:
        _starfield.stop()
    safe_print(f"\n{Theme.YELLOW}⚠ Mission aborted by operator{Theme.RESET}")
    sys.exit(0)


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx, version):
    """NASA Media Downloader - Download images and videos from NASA's library."""
    if version:
        from .. import __version__
        click.echo(f"NASA Media Downloader v{__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Default to interactive mode
        ctx.invoke(interactive)


@cli.command()
@click.option("--query", "-q", required=True, help="Search query")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option(
    "--quality",
    "-Q",
    default="orig",
    help="Qualities (1=small, 2=medium, 3=large, 4=orig, 5=all)",
)
@click.option("--limit", "-n", type=int, help="Maximum items to download")
@click.option("--rate", type=float, default=1.0, help="Rate limit in seconds")
@click.option("--workers", type=int, default=DEFAULT_WORKERS, help="Worker threads")
@click.option("--min-workers", type=int, default=MIN_WORKERS, help="Minimum workers")
@click.option("--max-workers", type=int, default=MAX_WORKERS, help="Maximum workers")
@click.option("--no-adaptive", is_flag=True, help="Disable adaptive throttling")
@click.option("--images/--no-images", default=True, help="Download images")
@click.option("--videos/--no-videos", default=False, help="Download videos")
@click.option("--metadata/--no-metadata", default=True, help="Save metadata")
def download(
    query,
    output,
    quality,
    limit,
    rate,
    workers,
    min_workers,
    max_workers,
    no_adaptive,
    images,
    videos,
    metadata,
):
    """Download NASA media with specified options (non-interactive)."""
    # Determine output directory
    if output:
        output_path = Path(output).expanduser()
    else:
        output_path = Path.cwd() / DEFAULT_SUBDIR

    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()

    # Parse qualities
    qualities = parse_quality_input(quality)

    # Run crawler
    crawl_nasa_media(
        query=query,
        main_save_dir=output_path,
        download_images=images,
        download_videos=videos,
        download_metadata=metadata,
        qualities=qualities,
        rate_limit=rate,
        max_items=limit,
        workers=workers,
        min_workers=min_workers,
        max_workers=max_workers,
        adaptive=not no_adaptive,
    )


@cli.command()
@click.option("--skip-intro", is_flag=True, help="Skip the intro animation")
@click.option("--rate", type=float, default=1.0, help="Rate limit in seconds")
@click.option("--workers", type=int, default=DEFAULT_WORKERS, help="Worker threads")
@click.option("--min-workers", type=int, default=MIN_WORKERS, help="Minimum workers")
@click.option("--max-workers", type=int, default=MAX_WORKERS, help="Maximum workers")
@click.option("--no-adaptive", is_flag=True, help="Disable adaptive throttling")
def interactive(skip_intro, rate, workers, min_workers, max_workers, no_adaptive):
    """Run in interactive mode with prompts and animations."""
    global _starfield

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start starfield
        _starfield = EnhancedStarfield(rows=5, density=0.055, interval=0.45)
        _starfield.start()

        # Show intro animation
        if not skip_intro:
            try:
                intro = SpaceIntro()
                intro.run_animation(duration=4.5, frames=50)
            except KeyboardInterrupt:
                pass

            time.sleep(0.5)
            clear_screen()

        # Configuration header
        safe_print(f"\n{Theme.BOLD}{Theme.CYAN}{'═' * 60}{Theme.RESET}")
        safe_print(f"{Theme.BOLD}{Theme.CYAN}  MISSION CONFIGURATION{Theme.RESET}")
        safe_print(f"{Theme.BOLD}{Theme.CYAN}{'═' * 60}{Theme.RESET}\n")

        # Get search query
        query = themed_input("Search query", "space exploration")

        # Get output directory
        script_dir = Path(__file__).resolve().parent.parent.parent.parent
        default_output = script_dir / DEFAULT_SUBDIR

        out_str = themed_input(
            f"Output folder (default: ./{DEFAULT_SUBDIR})",
            f"./{DEFAULT_SUBDIR}",
        )

        if out_str == f"./{DEFAULT_SUBDIR}":
            output_path = default_output
        else:
            output_path = Path(out_str).expanduser()

        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()

        # Quality selection
        qualities = show_quality_menu()

        # Media type selection
        download_images, download_videos = show_media_type_menu()

        # Metadata option
        download_metadata = show_metadata_menu()

        # Limit option
        max_items = show_limit_menu()

        # Confirm mission
        confirm_mission(
            query=query,
            output_path=str(output_path),
            qualities=qualities,
            download_images=download_images,
            download_videos=download_videos,
            download_metadata=download_metadata,
            max_items=max_items,
        )

        # Execute mission
        crawl_nasa_media(
            query=query,
            main_save_dir=output_path,
            download_images=download_images,
            download_videos=download_videos,
            download_metadata=download_metadata,
            qualities=qualities,
            rate_limit=rate,
            max_items=max_items,
            workers=workers,
            min_workers=min_workers,
            max_workers=max_workers,
            adaptive=not no_adaptive,
        )

    except KeyboardInterrupt:
        safe_print(f"\n{Theme.YELLOW}Mission terminated by operator{Theme.RESET}")
        sys.exit(0)
    finally:
        if _starfield:
            _starfield.stop()


def main(argv=None):
    """Main entry point for the application."""
    cli(argv)


if __name__ == "__main__":
    main()
