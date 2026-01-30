"""
Custom exceptions for NASA Media Downloader.
"""


class NasaDownloaderError(Exception):
    """Base exception for NASA Media Downloader."""
    pass


class APIError(NasaDownloaderError):
    """Raised when NASA API returns an error."""

    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class DownloadError(NasaDownloaderError):
    """Raised when a download fails."""

    def __init__(self, message: str, url: str = None, retries: int = 0):
        super().__init__(message)
        self.url = url
        self.retries = retries


class ConfigurationError(NasaDownloaderError):
    """Raised when configuration is invalid."""
    pass


class ThrottleError(NasaDownloaderError):
    """Raised when API rate limits are exceeded."""

    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class SecurityError(NasaDownloaderError):
    """Raised when a security violation is detected."""
    pass
