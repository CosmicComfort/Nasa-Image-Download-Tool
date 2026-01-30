"""
Main download engine and crawler orchestration.
"""

import json
import logging
import os
import re
import tempfile
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional
import sys

from ..core.config import (
    DEFAULT_SUBDIR,
    LOG_SUBDIR,
    LOG_FILENAME,
    DEFAULT_WORKERS,
    MAX_WORKERS,
    MIN_WORKERS,
    DEFAULT_RATE,
    QUALITY_LABELS,
)
from ..core.models import MissionManifest
from ..api.client import NasaAPI
from ..api.session import make_session
from ..api.quality import find_quality_urls
from ..ui.terminal import safe_print
from ..ui.themes import Theme
from .throttle import AdaptiveController
from .tasks import download_urls_concurrent
from .metadata import save_metadata_to_all_qualities


def sanitize_filename(s: str, max_len: int = 100) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        s: Input string
        max_len: Maximum length

    Returns:
        Sanitized filename string
    """
    if not s:
        return "item"

    s = s.strip().lower()
    # Remove unsafe characters (security: prevent path traversal)
    s = re.sub(r"[^\w\s\-_.()]", "", s)
    # Replace whitespace with underscores
    s = re.sub(r"\s+", "_", s)
    # Remove any remaining path separators
    s = s.replace("/", "").replace("\\", "")

    return s[:max_len] or "item"


def sanitize_search_query(query: str) -> str:
    """
    Sanitize a search query for security.

    Args:
        query: Raw search query

    Returns:
        Sanitized query string
    """
    # Remove potentially dangerous characters
    query = re.sub(r"[<>\"';\\]", "", query)
    # Limit length
    return query[:500].strip()


def ensure_writable_dir(path: Path) -> Path:
    """
    Ensure directory is writable, fallback to alternatives.

    Args:
        path: Preferred directory path

    Returns:
        Path to a writable directory
    """
    candidates = [
        path,
        Path.home() / DEFAULT_SUBDIR,
        Path(tempfile.gettempdir()) / f"{DEFAULT_SUBDIR}_temp",
    ]

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            with open(test_file, "w") as f:
                f.write("ok")
            test_file.unlink()
            return candidate.resolve()
        except Exception:
            continue

    return Path(tempfile.mkdtemp(prefix=f"{DEFAULT_SUBDIR}_")).resolve()


def configure_logging(base_dir: Path) -> None:
    """
    Configure logging to file and console.

    Args:
        base_dir: Base directory for log files
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logs_dir = base_dir / LOG_SUBDIR
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(logs_dir / LOG_FILENAME),
            maxBytes=3_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
    except Exception as exc:
        logging.warning("Could not enable file logging: %s", exc)


def write_mission_manifest(search_dir: Path, manifest: MissionManifest) -> None:
    """
    Write mission parameters to manifest file.

    Args:
        search_dir: Search output directory
        manifest: Mission manifest object
    """
    try:
        search_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = search_dir / "mission_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
        logging.info("Mission manifest: %s", manifest_path)
    except Exception as exc:
        logging.warning("Failed to write manifest: %s", exc)


def crawl_nasa_media(
    query: str,
    main_save_dir: Path,
    download_images: bool,
    download_videos: bool,
    download_metadata: bool,
    qualities: List[str],
    rate_limit: float = DEFAULT_RATE,
    max_items: Optional[int] = None,
    workers: int = DEFAULT_WORKERS,
    min_workers: int = MIN_WORKERS,
    max_workers: int = MAX_WORKERS,
    adaptive: bool = True,
) -> Dict:
    """
    Main crawler for NASA images and videos.

    Args:
        query: Search query
        main_save_dir: Main output directory
        download_images: Whether to download images
        download_videos: Whether to download videos
        download_metadata: Whether to save metadata
        qualities: List of quality levels to download
        rate_limit: Delay between API requests
        max_items: Maximum items to download per media type
        workers: Initial number of workers
        min_workers: Minimum workers for adaptive control
        max_workers: Maximum workers for adaptive control
        adaptive: Whether to use adaptive throttling

    Returns:
        Dictionary with download statistics
    """
    # Sanitize inputs (security)
    query = sanitize_search_query(query)

    # Setup directories
    main_save_dir = ensure_writable_dir(main_save_dir)
    sanitized_query = sanitize_filename(query) or "search"
    search_dir = main_save_dir / sanitized_query
    search_dir = ensure_writable_dir(search_dir)

    configure_logging(search_dir)

    # Create manifest
    manifest = MissionManifest(
        query=query,
        download_images=download_images,
        download_videos=download_videos,
        download_metadata=download_metadata,
        qualities=qualities,
        workers=workers,
        adaptive=adaptive,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        output_dir=str(search_dir),
        max_items=max_items,
    )
    write_mission_manifest(search_dir, manifest)

    logging.info("Mission initialized: %s", search_dir)
    logging.info("Workers: %d (adaptive: %s)", workers, adaptive)

    # Setup quality directories
    quality_dirs: Dict[str, Dict[str, Path]] = {}

    for quality in qualities:
        label = QUALITY_LABELS.get(quality, quality)

        if download_images:
            img_base = search_dir / "Images" / label
            (img_base / "Files").mkdir(parents=True, exist_ok=True)
            (img_base / "Metadata").mkdir(parents=True, exist_ok=True)
            quality_dirs.setdefault(quality, {})["images"] = img_base

        if download_videos:
            vid_base = search_dir / "Videos" / label
            (vid_base / "Files").mkdir(parents=True, exist_ok=True)
            (vid_base / "Metadata").mkdir(parents=True, exist_ok=True)
            quality_dirs.setdefault(quality, {})["videos"] = vid_base

    # API setup
    session = make_session(pool_maxsize=max(4, workers // 2))
    api = NasaAPI(session=session)
    controller = AdaptiveController(min_workers, max_workers) if adaptive else None

    current_workers = workers
    item_counter = 1
    total_img_downloaded = 0
    total_vid_downloaded = 0
    total_metadata = 0

    # Process images
    if download_images:
        safe_print(f"\n{Theme.CYAN}{'=' * 60}{Theme.RESET}")
        safe_print(f"{Theme.BOLD}{Theme.GREEN}PHASE 1: SCANNING FOR IMAGES{Theme.RESET}")
        safe_print(f"{Theme.CYAN}{'=' * 60}{Theme.RESET}\n")

        page = 1
        while True:
            logging.info("Fetching image page %d...", page)
            items, more = api.search(query=query, page=page, media_type="image")

            if not items:
                break

            page_downloads = []

            for item in items:
                if max_items and item_counter > max_items:
                    break

                nasa_id = item.nasa_id
                title = item.title
                filename_base = f"{item_counter:04d}_{sanitize_filename(title)[:60]}"

                urls = api.get_asset_urls(nasa_id)
                quality_urls = find_quality_urls(urls, qualities, "image")

                # Save metadata to ALL quality directories (FIXED)
                if download_metadata:
                    metadata = item.to_metadata_dict()
                    saved = save_metadata_to_all_qualities(
                        quality_dirs,
                        qualities,
                        filename_base,
                        metadata,
                        "images",
                    )
                    total_metadata += saved

                # Queue downloads
                for quality in qualities:
                    if quality in quality_urls and quality_urls[quality]:
                        for url in quality_urls[quality]:
                            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                            dest = (
                                quality_dirs[quality]["images"]
                                / "Files"
                                / f"{filename_base}{ext}"
                            )
                            if not dest.exists():
                                page_downloads.append((url, dest))

                safe_print(Theme.queued_image(title[:70]))
                item_counter += 1
                time.sleep(rate_limit)

                if max_items and item_counter > max_items:
                    break

            # Download batch
            if page_downloads:
                downloaded = download_urls_concurrent(
                    page_downloads, current_workers, controller
                )
                total_img_downloaded += downloaded

            # Adaptive adjustment
            if adaptive and controller:
                new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
                if new_workers != current_workers:
                    current_workers = new_workers
                if cooldown > 0:
                    time.sleep(cooldown)

            if not more or (max_items and item_counter > max_items):
                break

            page += 1

    # Process videos
    if download_videos:
        safe_print(f"\n{Theme.CYAN}{'=' * 60}{Theme.RESET}")
        safe_print(
            f"{Theme.BOLD}{Theme.MAGENTA}PHASE 2: SCANNING FOR VIDEOS{Theme.RESET}"
        )
        safe_print(f"{Theme.CYAN}{'=' * 60}{Theme.RESET}\n")

        page = 1
        video_counter = 1

        while True:
            logging.info("Fetching video page %d...", page)
            items, more = api.search(query=query, page=page, media_type="video")

            if not items:
                break

            page_downloads = []

            for item in items:
                if max_items and video_counter > max_items:
                    break

                nasa_id = item.nasa_id
                title = item.title
                filename_base = f"{video_counter:04d}_{sanitize_filename(title)[:60]}"

                urls = api.get_asset_urls(nasa_id)
                quality_urls = find_quality_urls(urls, qualities, "video")

                # Save metadata to ALL quality directories (FIXED)
                if download_metadata:
                    metadata = item.to_metadata_dict()
                    saved = save_metadata_to_all_qualities(
                        quality_dirs,
                        qualities,
                        filename_base,
                        metadata,
                        "videos",
                    )
                    total_metadata += saved

                # Queue downloads
                for quality in qualities:
                    if quality in quality_urls and quality_urls[quality]:
                        for url in quality_urls[quality]:
                            ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
                            dest = (
                                quality_dirs[quality]["videos"]
                                / "Files"
                                / f"{filename_base}{ext}"
                            )
                            if not dest.exists():
                                page_downloads.append((url, dest))

                safe_print(Theme.queued_video(title[:70]))
                video_counter += 1
                time.sleep(rate_limit)

                if max_items and video_counter > max_items:
                    break

            # Download batch
            if page_downloads:
                downloaded = download_urls_concurrent(
                    page_downloads, current_workers, controller
                )
                total_vid_downloaded += downloaded

            # Adaptive adjustment
            if adaptive and controller:
                new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
                if new_workers != current_workers:
                    current_workers = new_workers
                if cooldown > 0:
                    time.sleep(cooldown)

            if not more or (max_items and video_counter > max_items):
                break

            page += 1

    # Summary
    safe_print(f"\n{Theme.CYAN}{'=' * 60}{Theme.RESET}")
    safe_print(f"{Theme.BOLD}{Theme.GREEN}MISSION COMPLETE{Theme.RESET}")
    safe_print(f"{Theme.CYAN}{'=' * 60}{Theme.RESET}")
    safe_print(f"  Images downloaded: {total_img_downloaded}")
    safe_print(f"  Videos downloaded: {total_vid_downloaded}")
    safe_print(f"  Metadata files: {total_metadata}")
    safe_print(f"  Output location: {search_dir}")
    safe_print(f"{Theme.CYAN}{'=' * 60}{Theme.RESET}\n")

    # Cleanup
    api.close()

    return {
        "images_downloaded": total_img_downloaded,
        "videos_downloaded": total_vid_downloaded,
        "metadata_files": total_metadata,
        "output_dir": str(search_dir),
    }
