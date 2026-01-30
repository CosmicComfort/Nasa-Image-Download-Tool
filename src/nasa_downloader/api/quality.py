"""
Quality selection and URL scoring for NASA media.

This module contains the FIXED video quality detection that uses intelligent
scoring instead of simple string matching.
"""

import re
from typing import Dict, List, Optional, Tuple

from ..core.config import (
    QUALITY_SUFFIXES,
    VIDEO_EXTENSIONS,
    VIDEO_QUALITY_PATTERNS,
)


def score_video_url(url: str, target_quality: str) -> int:
    """
    Score a video URL based on how well it matches the target quality.

    Uses intelligent pattern matching including:
    - Resolution patterns (1080p, 720p, 480p, etc.)
    - Quality keywords (orig, master, preview, etc.)
    - File size indicators
    - Codec information

    Args:
        url: The video URL to score
        target_quality: Target quality level (small, medium, large, orig)

    Returns:
        Score indicating match quality (higher is better)
    """
    url_lower = url.lower()
    score = 0

    # Get patterns for target quality
    patterns = VIDEO_QUALITY_PATTERNS.get(target_quality, {})
    keywords = patterns.get("keywords", [])
    resolutions = patterns.get("resolutions", [])
    score_boost = patterns.get("score_boost", 0)

    # Check for keyword matches
    for keyword in keywords:
        if keyword in url_lower:
            score += 30

    # Check for resolution matches
    for resolution in resolutions:
        if resolution in url_lower:
            score += 50

    # Extract resolution from URL if present
    resolution_match = re.search(r"(\d{3,4})x(\d{3,4})", url_lower)
    if resolution_match:
        width = int(resolution_match.group(1))
        height = int(resolution_match.group(2))
        pixels = width * height

        # Map pixel count to quality
        if target_quality == "orig" and pixels >= 1920 * 1080:
            score += 40
        elif target_quality == "large" and 1280 * 720 <= pixels < 1920 * 1080:
            score += 40
        elif target_quality == "medium" and 854 * 480 <= pixels < 1280 * 720:
            score += 40
        elif target_quality == "small" and pixels < 854 * 480:
            score += 40

    # Check for p-notation (1080p, 720p, etc.)
    p_match = re.search(r"(\d{3,4})p", url_lower)
    if p_match:
        p_value = int(p_match.group(1))
        if target_quality == "orig" and p_value >= 1080:
            score += 45
        elif target_quality == "large" and 720 <= p_value < 1080:
            score += 45
        elif target_quality == "medium" and 480 <= p_value < 720:
            score += 45
        elif target_quality == "small" and p_value < 480:
            score += 45

    # Penalize mismatches
    other_qualities = [q for q in VIDEO_QUALITY_PATTERNS if q != target_quality]
    for other_q in other_qualities:
        other_patterns = VIDEO_QUALITY_PATTERNS[other_q]
        for keyword in other_patterns.get("keywords", []):
            if keyword in url_lower and keyword not in keywords:
                score -= 20

    # Apply quality-specific boost
    score += score_boost

    return max(0, score)


def find_best_video_url(
    urls: List[str], target_quality: str
) -> Optional[Tuple[str, int]]:
    """
    Find the best video URL for a target quality.

    Args:
        urls: List of video URLs to choose from
        target_quality: Target quality level

    Returns:
        Tuple of (best_url, score) or None if no video URLs found
    """
    video_urls = [
        u for u in urls if any(u.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
    ]

    if not video_urls:
        return None

    scored = [(url, score_video_url(url, target_quality)) for url in video_urls]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[0] if scored else None


def find_quality_urls(
    urls: List[str], qualities: List[str], media_type: str
) -> Dict[str, List[str]]:
    """
    Find URLs for requested qualities based on media type.

    This is the FIXED version that uses intelligent scoring for videos.

    Args:
        urls: List of available URLs
        qualities: List of requested quality levels
        media_type: Either "image" or "video"

    Returns:
        Dictionary mapping quality -> list of URLs
    """
    result = {q: [] for q in qualities}

    if media_type == "video":
        video_urls = [
            u for u in urls if any(u.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        ]

        if not video_urls:
            return result

        for quality in qualities:
            # Score all video URLs for this quality
            scored = [
                (url, score_video_url(url, quality)) for url in video_urls
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Take the best match if it has a reasonable score
            if scored:
                best_url, best_score = scored[0]
                # Use the best URL if it has any positive score,
                # or fallback to first video URL if no matches
                if best_score > 0:
                    result[quality] = [best_url]
                elif video_urls:
                    # Fallback: use first available video
                    result[quality] = [video_urls[0]]

    else:  # images
        for quality in qualities:
            suffix = QUALITY_SUFFIXES.get(quality, "")
            matches = [u for u in urls if suffix in u.lower()]
            if matches:
                result[quality] = matches[:1]
            elif quality == "orig":
                # For orig, also check for URLs without any quality suffix
                non_qualified = [
                    u
                    for u in urls
                    if not any(s in u.lower() for s in QUALITY_SUFFIXES.values())
                    and any(
                        u.lower().endswith(ext)
                        for ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff")
                    )
                ]
                if non_qualified:
                    result[quality] = non_qualified[:1]

    return result
