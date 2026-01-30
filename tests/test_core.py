"""Tests for core modules."""

import pytest
from nasa_downloader.core.config import (
    DEFAULT_SUBDIR,
    QUALITY_SUFFIXES,
    VIDEO_QUALITY_PATTERNS,
)
from nasa_downloader.core.models import NasaItem, DownloadResult, MissionManifest
from nasa_downloader.core.exceptions import (
    NasaDownloaderError,
    APIError,
    DownloadError,
)


class TestConfig:
    """Tests for configuration module."""

    def test_default_subdir_exists(self):
        assert DEFAULT_SUBDIR == "NASA-Downloads"

    def test_quality_suffixes(self):
        assert "small" in QUALITY_SUFFIXES
        assert "medium" in QUALITY_SUFFIXES
        assert "large" in QUALITY_SUFFIXES
        assert "orig" in QUALITY_SUFFIXES

    def test_video_quality_patterns(self):
        assert "orig" in VIDEO_QUALITY_PATTERNS
        assert "large" in VIDEO_QUALITY_PATTERNS
        assert "medium" in VIDEO_QUALITY_PATTERNS
        assert "small" in VIDEO_QUALITY_PATTERNS


class TestModels:
    """Tests for data models."""

    def test_nasa_item_creation(self):
        item = NasaItem(
            nasa_id="TEST123",
            title="Test Image",
            description="A test description",
            date_created="2024-01-01",
            center="JPL",
            keywords=["test", "space"],
            media_type="image",
            raw={},
        )
        assert item.nasa_id == "TEST123"
        assert item.title == "Test Image"
        assert item.media_type == "image"

    def test_nasa_item_to_metadata(self):
        item = NasaItem(
            nasa_id="TEST123",
            title="Test Image",
            description="A test description",
            date_created="2024-01-01",
            center="JPL",
            keywords=["test", "space"],
            media_type="image",
            raw={},
        )
        metadata = item.to_metadata_dict()
        assert metadata["NASA ID"] == "TEST123"
        assert metadata["Title"] == "Test Image"
        assert "test, space" in metadata["Keywords"]

    def test_download_result(self):
        from pathlib import Path

        result = DownloadResult(
            url="https://example.com/image.jpg",
            destination=Path("/tmp/image.jpg"),
            success=True,
            bytes_downloaded=1024,
        )
        assert result.success is True
        assert result.filename == "image.jpg"

    def test_mission_manifest(self):
        manifest = MissionManifest(
            query="mars",
            download_images=True,
            download_videos=False,
            download_metadata=True,
            qualities=["orig", "large"],
            workers=6,
            adaptive=True,
            timestamp="2024-01-01T00:00:00Z",
        )
        data = manifest.to_dict()
        assert data["query"] == "mars"
        assert data["download_images"] is True
        assert "orig" in data["qualities"]


class TestExceptions:
    """Tests for custom exceptions."""

    def test_api_error(self):
        error = APIError("API failed", status_code=404)
        assert "API failed" in str(error)
        assert error.status_code == 404

    def test_download_error(self):
        error = DownloadError("Download failed", url="https://example.com", retries=3)
        assert "Download failed" in str(error)
        assert error.url == "https://example.com"
        assert error.retries == 3
