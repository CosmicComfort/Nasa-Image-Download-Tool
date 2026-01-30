"""
Data models for NASA Media Downloader.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class NasaItem:
    """Represents a NASA media item from the API."""

    nasa_id: str
    title: str
    description: str
    date_created: str
    center: str
    keywords: List[str]
    media_type: str  # "image" or "video"
    raw: Dict = field(default_factory=dict)

    def to_metadata_dict(self) -> Dict:
        """Convert to dictionary suitable for metadata saving."""
        return {
            "NASA ID": self.nasa_id,
            "Title": self.title,
            "Description": self.description,
            "Date": self.date_created,
            "Center": self.center,
            "Keywords": ", ".join(self.keywords) if self.keywords else "",
            "Media Type": self.media_type,
        }


@dataclass
class DownloadResult:
    """Result of a download operation."""

    url: str
    destination: Path
    success: bool
    error: Optional[str] = None
    bytes_downloaded: int = 0

    @property
    def filename(self) -> str:
        """Get the filename from the destination path."""
        return self.destination.name


@dataclass
class QualityUrl:
    """Represents a URL with its detected quality."""

    url: str
    quality: str
    score: int
    media_type: str

    def __lt__(self, other: "QualityUrl") -> bool:
        """Allow sorting by score (higher is better)."""
        return self.score < other.score


@dataclass
class MissionManifest:
    """Mission configuration and parameters."""

    query: str
    download_images: bool
    download_videos: bool
    download_metadata: bool
    qualities: List[str]
    workers: int
    adaptive: bool
    timestamp: str
    output_dir: Optional[str] = None
    max_items: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "download_images": self.download_images,
            "download_videos": self.download_videos,
            "download_metadata": self.download_metadata,
            "qualities": self.qualities,
            "workers": self.workers,
            "adaptive": self.adaptive,
            "timestamp": self.timestamp,
            "output_dir": self.output_dir,
            "max_items": self.max_items,
        }
