"""
NASA API client for searching and retrieving media.
"""

import logging
from typing import List, Optional, Tuple

import requests

from ..core.config import API_SEARCH_URL, API_ASSET_URL, REQUEST_TIMEOUT
from ..core.models import NasaItem
from ..core.exceptions import APIError
from .session import make_session


class NasaAPI:
    """Client for interacting with NASA's Images API."""

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize the NASA API client.

        Args:
            session: Optional requests session (creates one if not provided)
        """
        self.session = session or make_session()
        self.logger = logging.getLogger(__name__)

    def search(
        self, query: str, page: int = 1, media_type: str = "image"
    ) -> Tuple[List[NasaItem], bool]:
        """
        Search for NASA media items.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            media_type: Type of media ("image" or "video")

        Returns:
            Tuple of (list of NasaItem, has_more_pages)

        Raises:
            APIError: If the API request fails
        """
        try:
            response = self.session.get(
                API_SEARCH_URL,
                params={"q": query, "media_type": media_type, "page": page},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            payload = response.json()
            items = payload.get("collection", {}).get("items", [])

            results = []
            for item in items:
                data = item.get("data", [{}])[0]
                results.append(
                    NasaItem(
                        nasa_id=data.get("nasa_id", "unknown"),
                        title=data.get("title", "No Title"),
                        description=data.get("description", ""),
                        date_created=data.get("date_created", ""),
                        center=data.get("center", ""),
                        keywords=data.get("keywords", []) or [],
                        media_type=data.get("media_type", media_type),
                        raw=data,
                    )
                )

            has_more = len(items) > 0
            return results, has_more

        except requests.exceptions.HTTPError as e:
            self.logger.error("Search failed for page %d: %s", page, e)
            raise APIError(
                f"Search failed: {e}",
                status_code=e.response.status_code if e.response else None,
            )
        except requests.exceptions.RequestException as e:
            self.logger.error("Search request failed for page %d: %s", page, e)
            return [], False
        except Exception as e:
            self.logger.error("Unexpected error during search: %s", e)
            return [], False

    def get_asset_urls(self, nasa_id: str) -> List[str]:
        """
        Get all asset URLs for a NASA item.

        Args:
            nasa_id: NASA ID of the item

        Returns:
            List of asset URLs
        """
        try:
            response = self.session.get(
                f"{API_ASSET_URL}/{nasa_id}",
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            payload = response.json()
            items = payload.get("collection", {}).get("items", [])
            urls = [item.get("href") for item in items if item.get("href")]

            return urls

        except Exception as e:
            self.logger.warning("Failed to get assets for %s: %s", nasa_id, e)
            return []

    def close(self) -> None:
        """Close the API client session."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
