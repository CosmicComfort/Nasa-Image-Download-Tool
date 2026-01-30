"""
Configuration constants and settings for NASA Media Downloader.
"""

# Directory defaults
DEFAULT_SUBDIR = "NASA-Downloads"
LOG_SUBDIR = "logs"
LOG_FILENAME = "nasa_downloader.log"

# NASA API endpoints (HTTPS only for security)
API_BASE_URL = "https://images-api.nasa.gov"
API_SEARCH_URL = f"{API_BASE_URL}/search"
API_ASSET_URL = f"{API_BASE_URL}/asset"

# Quality suffixes for image URLs
QUALITY_SUFFIXES = {
    "small": "~small",
    "medium": "~medium",
    "large": "~large",
    "orig": "~orig",
}

# Human-readable quality labels
QUALITY_LABELS = {
    "small": "Low",
    "medium": "Medium",
    "large": "High",
    "orig": "Original",
}

# Network defaults
DEFAULT_WORKERS = 6
MAX_WORKERS = 12
MIN_WORKERS = 1
DEFAULT_RATE = 1.0
RETRY_TOTAL = 3
RETRY_BACKOFF = 0.5
REQUEST_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 45
CHUNK_SIZE = 65536

# User-Agent for API requests
USER_AGENT = "nasa-media-downloader/2.1.0 (https://github.com/nasa-media-downloader)"

# Video file extensions
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".webm", ".m4v", ".mkv")

# Image file extensions
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp")

# Video quality scoring patterns
VIDEO_QUALITY_PATTERNS = {
    "orig": {
        "keywords": ["orig", "original", "master", "source", "full"],
        "resolutions": ["4k", "2160p", "uhd"],
        "score_boost": 100,
    },
    "large": {
        "keywords": ["large", "hd", "high", "1080"],
        "resolutions": ["1080p", "1920x1080", "fhd"],
        "score_boost": 75,
    },
    "medium": {
        "keywords": ["medium", "web", "720", "standard"],
        "resolutions": ["720p", "1280x720", "hd"],
        "score_boost": 50,
    },
    "small": {
        "keywords": ["small", "mobile", "preview", "thumb", "low", "480", "360"],
        "resolutions": ["480p", "360p", "sd"],
        "score_boost": 25,
    },
}
