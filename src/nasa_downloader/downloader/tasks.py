"""
Download task logic and concurrent download management.
"""

import concurrent.futures
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

from tqdm import tqdm

from ..core.config import CHUNK_SIZE, DOWNLOAD_TIMEOUT, DEFAULT_WORKERS
from ..api.session import get_thread_session
from .throttle import AdaptiveController


def download_file(
    url: str,
    dest: Path,
    controller: Optional[AdaptiveController] = None,
    chunk_size: int = CHUNK_SIZE,
    retries: int = 3,
) -> bool:
    """
    Download a file from URL to destination.

    Args:
        url: Source URL
        dest: Destination path
        controller: Optional adaptive controller for reporting
        chunk_size: Download chunk size in bytes
        retries: Number of retry attempts

    Returns:
        True if download succeeded, False otherwise
    """
    logger = logging.getLogger(__name__)
    session = get_thread_session(pool_maxsize=10)

    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
                # Handle throttling
                if response.status_code == 429:
                    if controller:
                        controller.report("throttle")
                    sleep_time = min(30, 2**attempt)
                    logger.warning(
                        "Rate limited (429), waiting %ds before retry", sleep_time
                    )
                    time.sleep(sleep_time)
                    continue

                response.raise_for_status()

                # Ensure parent directory exists
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Download file
                with open(dest, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)

                if controller:
                    controller.report("success")

                return True

        except Exception as exc:
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt,
                retries,
                url,
                exc,
            )
            sleep_time = min(10, 0.5 * (2**attempt))
            time.sleep(sleep_time)

    if controller:
        controller.report("fail")

    return False


def download_urls_concurrent(
    url_dest_pairs: List[Tuple[str, Path]],
    workers: int = DEFAULT_WORKERS,
    controller: Optional[AdaptiveController] = None,
    show_progress: bool = True,
) -> int:
    """
    Download multiple files concurrently.

    Args:
        url_dest_pairs: List of (url, destination_path) tuples
        workers: Number of concurrent workers
        controller: Optional adaptive controller
        show_progress: Whether to show progress bar

    Returns:
        Number of successful downloads
    """
    if not url_dest_pairs:
        return 0

    logger = logging.getLogger(__name__)
    success_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(download_file, url, dest, controller)
            for url, dest in url_dest_pairs
        ]

        iterator = concurrent.futures.as_completed(futures)
        if show_progress:
            iterator = tqdm(
                iterator,
                total=len(futures),
                desc="Downloading",
                unit="file",
            )

        for future in iterator:
            try:
                if future.result():
                    success_count += 1
            except Exception as exc:
                logger.exception("Download error: %s", exc)

    return success_count
