"""
HTTP session management for NASA API requests.
"""

import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..core.config import RETRY_TOTAL, RETRY_BACKOFF, USER_AGENT

# Thread-local storage for sessions
_thread_local = threading.local()


def make_session(
    pool_maxsize: int = 10,
    retries: int = RETRY_TOTAL,
    backoff_factor: float = RETRY_BACKOFF,
) -> requests.Session:
    """
    Create a requests session with retry logic and connection pooling.

    Args:
        pool_maxsize: Maximum pool size for connections
        retries: Number of retries for failed requests
        backoff_factor: Exponential backoff factor for retries

    Returns:
        Configured requests.Session instance
    """
    session = requests.Session()

    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
    )

    adapter = HTTPAdapter(
        pool_connections=pool_maxsize,
        pool_maxsize=pool_maxsize,
        max_retries=retry,
    )

    # Only mount HTTPS adapter (security: enforce HTTPS)
    session.mount("https://", adapter)

    # Set proper User-Agent
    session.headers.update({"User-Agent": USER_AGENT})

    return session


def get_thread_session(pool_maxsize: int = 10) -> requests.Session:
    """
    Get or create a thread-local session.

    This ensures each thread has its own session for thread safety.

    Args:
        pool_maxsize: Maximum pool size for connections

    Returns:
        Thread-local requests.Session instance
    """
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session(pool_maxsize=pool_maxsize)
    return _thread_local.session


def close_thread_session() -> None:
    """Close the thread-local session if it exists."""
    if hasattr(_thread_local, "session"):
        try:
            _thread_local.session.close()
        except Exception:
            pass
        delattr(_thread_local, "session")
