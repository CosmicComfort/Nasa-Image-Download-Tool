"""Tests for quality selection module (including bug fix verification)."""

import pytest
from nasa_downloader.api.quality import (
    score_video_url,
    find_best_video_url,
    find_quality_urls,
)


class TestVideoQualityScoring:
    """Tests for video quality scoring (Bug Fix #2)."""

    def test_score_1080p_url_for_large(self):
        url = "https://example.com/video_1080p.mp4"
        score = score_video_url(url, "large")
        assert score > 0

    def test_score_720p_url_for_medium(self):
        url = "https://example.com/video_720p.mp4"
        score = score_video_url(url, "medium")
        assert score > 0

    def test_score_480p_url_for_small(self):
        url = "https://example.com/video_480p.mp4"
        score = score_video_url(url, "small")
        assert score > 0

    def test_score_original_url(self):
        url = "https://example.com/video_orig_master.mp4"
        score = score_video_url(url, "orig")
        assert score > 0

    def test_score_url_with_resolution(self):
        url = "https://example.com/video_1920x1080.mp4"
        score = score_video_url(url, "orig")
        assert score > 0

    def test_hd_keyword_scores_for_large(self):
        url = "https://example.com/video_hd.mp4"
        score = score_video_url(url, "large")
        assert score > 0

    def test_mobile_keyword_scores_for_small(self):
        url = "https://example.com/video_mobile.mp4"
        score = score_video_url(url, "small")
        assert score > 0

    def test_preview_keyword_scores_for_small(self):
        url = "https://example.com/video_preview.mp4"
        score = score_video_url(url, "small")
        assert score > 0


class TestFindBestVideoUrl:
    """Tests for finding best video URL."""

    def test_find_best_from_multiple_urls(self):
        urls = [
            "https://example.com/video_480p.mp4",
            "https://example.com/video_720p.mp4",
            "https://example.com/video_1080p.mp4",
        ]
        result = find_best_video_url(urls, "large")
        assert result is not None
        url, score = result
        assert "1080p" in url or "720p" in url

    def test_find_best_returns_none_for_no_videos(self):
        urls = [
            "https://example.com/image.jpg",
            "https://example.com/metadata.json",
        ]
        result = find_best_video_url(urls, "orig")
        assert result is None


class TestFindQualityUrls:
    """Tests for finding quality URLs."""

    def test_find_image_quality_urls(self):
        urls = [
            "https://example.com/image~small.jpg",
            "https://example.com/image~medium.jpg",
            "https://example.com/image~large.jpg",
            "https://example.com/image~orig.jpg",
        ]
        result = find_quality_urls(urls, ["small", "large"], "image")
        assert "small" in result
        assert "large" in result
        assert len(result["small"]) > 0
        assert len(result["large"]) > 0

    def test_find_video_quality_urls(self):
        urls = [
            "https://example.com/video_mobile.mp4",
            "https://example.com/video_web.mp4",
            "https://example.com/video_hd.mp4",
            "https://example.com/video_orig.mp4",
        ]
        result = find_quality_urls(urls, ["small", "orig"], "video")
        assert "small" in result
        assert "orig" in result

    def test_fallback_to_available_video(self):
        """Test that videos fall back to available URL when no quality matches."""
        urls = [
            "https://example.com/video.mp4",
        ]
        result = find_quality_urls(urls, ["orig"], "video")
        assert len(result["orig"]) > 0
