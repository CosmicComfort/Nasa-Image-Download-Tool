"""Tests for metadata saving (including bug fix verification)."""

import pytest
import tempfile
from pathlib import Path
from nasa_downloader.downloader.metadata import (
    save_metadata,
    save_metadata_to_all_qualities,
)


class TestSaveMetadata:
    """Tests for basic metadata saving."""

    def test_save_metadata_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir)
            metadata = {
                "NASA ID": "TEST123",
                "Title": "Test Image",
                "Description": "A test",
            }

            json_path, txt_path = save_metadata(dest_dir, "test_file", metadata)

            assert json_path.exists()
            assert txt_path.exists()

    def test_save_metadata_json_content(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir)
            metadata = {"key": "value"}

            json_path, _ = save_metadata(dest_dir, "test", metadata)

            with open(json_path) as f:
                loaded = json.load(f)
            assert loaded["key"] == "value"

    def test_save_metadata_txt_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir)
            metadata = {"key": "value"}

            _, txt_path = save_metadata(dest_dir, "test", metadata)

            content = txt_path.read_text()
            assert "key: value" in content


class TestSaveMetadataToAllQualities:
    """Tests for saving metadata to all quality directories (Bug Fix #1)."""

    def test_saves_to_all_qualities(self):
        """Verify metadata is saved to ALL quality directories, not just the first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create quality directories
            quality_dirs = {}
            for quality in ["small", "medium", "large", "orig"]:
                quality_path = base / quality
                (quality_path / "Files").mkdir(parents=True)
                (quality_path / "Metadata").mkdir(parents=True)
                quality_dirs[quality] = {"images": quality_path}

            metadata = {"NASA ID": "TEST", "Title": "Test"}
            qualities = ["small", "medium", "large", "orig"]

            saved = save_metadata_to_all_qualities(
                quality_dirs, qualities, "test_file", metadata, "images"
            )

            # Should save to all 4 directories
            assert saved == 4

            # Verify each directory has metadata
            for quality in qualities:
                json_file = quality_dirs[quality]["images"] / "Metadata" / "test_file.json"
                txt_file = quality_dirs[quality]["images"] / "Metadata" / "test_file.txt"
                assert json_file.exists(), f"Missing JSON in {quality}"
                assert txt_file.exists(), f"Missing TXT in {quality}"

    def test_handles_missing_quality(self):
        """Verify graceful handling when a quality directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Only create one quality directory
            quality_dirs = {
                "orig": {"images": base / "orig"}
            }
            (base / "orig" / "Metadata").mkdir(parents=True)

            metadata = {"NASA ID": "TEST"}
            qualities = ["small", "orig"]  # Request small too, but it doesn't exist

            saved = save_metadata_to_all_qualities(
                quality_dirs, qualities, "test", metadata, "images"
            )

            # Should only save to the one that exists
            assert saved == 1
