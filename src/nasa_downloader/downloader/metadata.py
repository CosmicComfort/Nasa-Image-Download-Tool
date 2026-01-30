"""
Metadata saving utilities.

This module contains the FIXED metadata saving that properly saves to ALL
quality directories, not just the first one.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def save_metadata(
    dest_dir: Path, filename_base: str, metadata: Dict
) -> Tuple[Path, Path]:
    """
    Save metadata as JSON and TXT files.

    Args:
        dest_dir: Destination directory for metadata files
        filename_base: Base filename (without extension)
        metadata: Dictionary of metadata to save

    Returns:
        Tuple of (json_path, txt_path)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    json_path = dest_dir / f"{filename_base}.json"
    txt_path = dest_dir / f"{filename_base}.txt"

    # Save JSON
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Failed to save JSON metadata: %s", exc)

    # Save human-readable TXT
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            for key, value in metadata.items():
                f.write(f"{key}: {value}\n")
    except Exception as exc:
        logger.warning("Failed to save TXT metadata: %s", exc)

    return json_path, txt_path


def save_metadata_to_all_qualities(
    quality_dirs: Dict[str, Dict[str, Path]],
    qualities: List[str],
    filename_base: str,
    metadata: Dict,
    media_type: str,
) -> int:
    """
    Save metadata to ALL selected quality directories.

    This is the FIXED version that iterates through all qualities
    instead of only saving to qualities[0].

    Args:
        quality_dirs: Dictionary mapping quality -> {"images": Path, "videos": Path}
        qualities: List of selected quality levels
        filename_base: Base filename for metadata files
        metadata: Metadata dictionary to save
        media_type: Either "images" or "videos"

    Returns:
        Number of directories where metadata was saved
    """
    saved_count = 0

    for quality in qualities:
        if quality not in quality_dirs:
            continue

        quality_paths = quality_dirs[quality]
        if media_type not in quality_paths:
            continue

        base_path = quality_paths[media_type]
        meta_dir = base_path / "Metadata"

        try:
            save_metadata(meta_dir, filename_base, metadata)
            saved_count += 1
            logger.debug(
                "Saved metadata to %s quality: %s",
                quality,
                meta_dir,
            )
        except Exception as exc:
            logger.warning(
                "Failed to save metadata to %s quality: %s",
                quality,
                exc,
            )

    return saved_count
