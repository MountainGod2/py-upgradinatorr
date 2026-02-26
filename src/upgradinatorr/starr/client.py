"""Starr application API client."""

import asyncio
import logging
from http import HTTPStatus
from types import TracebackType
from typing import Any, ClassVar, Self, cast

import aiohttp

from upgradinatorr.config import get_application_type

logger = logging.getLogger(__name__)


class StarrAPIError(Exception):
    """Raised when Starr API returns an error."""

    def __init__(self, status: int, message: str, application: str) -> None:
        """Initialize API error with status, message, and application name."""
        self.status = status
        self.message = message
        self.application = application
        super().__init__(f"{application} responded with {status}: {message}")


class StarrClient:
    """Async client for interacting with Starr application APIs."""

    ENDPOINTS: ClassVar = {
        "radarr": "movie",
        "sonarr": "series",
        "lidarr": "artist",
        "readarr": "author",
    }

    SEARCH_COMMANDS: ClassVar = {
        "radarr": "MoviesSearch",
        "sonarr": "SeriesSearch",
        "lidarr": "ArtistSearch",
        "readarr": "AuthorSearch",
    }

    EDITOR_ENDPOINTS: ClassVar = {
        "radarr": ("movie/editor", "movieIds"),
        "sonarr": ("series/editor", "seriesIds"),
        "lidarr": ("artist/editor", "artistIds"),
        "readarr": ("author/editor", "authorIds"),
    }

    ERROR_MESSAGES: ClassVar[dict[int, str]] = {
        302: "Redirect - are you missing a URL base path?",
        400: "Bad Request - check your configuration",
        401: "Unauthorized - check your API key",
        404: "Not Found - check your URL",
        409: "Conflict - check your configuration",
        500: "Internal Server Error",
    }

    def __init__(self, app_name: str, url: str, api_key: str) -> None:
        """Initialize Starr client.

        Args:
            app_name: Name of the application (radarr, sonarr, lidarr, readarr)
            url: Base URL of the application
            api_key: API key for authentication

        """
        self.app_name = get_application_type(app_name)
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.api_version: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
        )
        self.api_version = await self._get_api_version()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make HTTP request to Starr API.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to aiohttp

        Returns:
            JSON response from API

        Raises:
            StarrAPIError: If API returns an error status

        """
        if not self._session:
            msg = "Client not initialized. Use async with statement."
            raise RuntimeError(msg)

        url = f"{self.base_url}/api/{self.api_version}/{endpoint}"

        async with self._session.request(method, url, **kwargs) as response:
            if not response.ok:
                message = self.ERROR_MESSAGES.get(
                    response.status,
                    f"unexpected status {response.status}",
                )
                raise StarrAPIError(response.status, message, self.app_name)

            return cast("dict[str, Any] | list[dict[str, Any]]", await response.json())

    async def _get_api_version(self) -> str:
        """Get current API version from application."""
        if not self._session:
            msg = "Client not initialized"
            raise RuntimeError(msg)

        url = f"{self.base_url}/api"
        async with self._session.get(url) as response:
            if not (HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES):
                raise StarrAPIError(response.status, "failed to get API version", self.app_name)
            data = await response.json()
            return cast("str", data["current"])

    async def get_all_media(self) -> list[dict[str, Any]]:
        """Get all media items from the application."""
        endpoint = self.ENDPOINTS[self.app_name]
        media = await self._request("GET", endpoint)
        return media if isinstance(media, list) else []

    async def get_tag(self, tag_name: str) -> dict[str, Any] | None:
        """Get tag by name, returns None if not found."""
        tags = await self._request("GET", "tag")
        if isinstance(tags, list):
            for tag in tags:
                if tag.get("label") == tag_name:
                    return tag
        return None

    async def create_tag(self, tag_name: str) -> dict[str, Any]:
        """Create a new tag."""
        result = await self._request("POST", "tag", json={"label": tag_name})
        return result if isinstance(result, dict) else {}

    async def get_or_create_tag(self, tag_name: str) -> int:
        """Get tag ID, creating it if it doesn't exist."""
        tag = await self.get_tag(tag_name)
        if tag:
            return int(tag["id"])
        new_tag = await self.create_tag(tag_name)
        return int(new_tag["id"])

    async def get_quality_profile_id(self, profile_name: str) -> int:
        """Get quality profile ID by name."""
        profiles = await self._request("GET", "qualityprofile")
        if isinstance(profiles, list):
            for profile in profiles:
                if profile.get("name") == profile_name:
                    return int(profile["id"])
        msg = f"quality profile '{profile_name}' not found in {self.app_name}"
        raise ValueError(msg)

    async def add_tags_to_media(self, media_ids: list[int], tag_id: int) -> None:
        """Add tag to multiple media items."""
        endpoint, id_key = self.EDITOR_ENDPOINTS[self.app_name]
        await self._request(
            "PUT",
            endpoint,
            json={id_key: media_ids, "tags": [tag_id], "applyTags": "add"},
        )

    async def remove_tags_from_media(self, media_ids: list[int], tag_id: int) -> None:
        """Remove tag from multiple media items."""
        endpoint, id_key = self.EDITOR_ENDPOINTS[self.app_name]
        await self._request(
            "PUT",
            endpoint,
            json={id_key: media_ids, "tags": [tag_id], "applyTags": "remove"},
        )

    async def search_media(self, media_id: int) -> None:
        """Trigger search for a single media item."""
        command = self.SEARCH_COMMANDS[self.app_name]
        if self.app_name == "radarr":
            body: dict[str, Any] = {"name": command, "movieIds": [media_id]}
        else:
            object_name = self.ENDPOINTS[self.app_name]
            body = {"name": command, f"{object_name}Id": media_id}
        await self._request("POST", "command", json=body)

    async def search_media_batch(self, media_items: list[dict[str, Any]]) -> None:
        """Search for multiple media items.

        Radarr supports batch search; Sonarr, Lidarr, and Readarr require individual requests
        dispatched concurrently via a semaphore-limited gather.
        """
        if self.app_name == "radarr":
            media_ids = [item["id"] for item in media_items]
            await self._request(
                "POST",
                "command",
                json={"name": "MoviesSearch", "movieIds": media_ids},
            )
        else:
            semaphore = asyncio.Semaphore(10)

            async def _search(media_id: int) -> None:
                async with semaphore:
                    await self.search_media(media_id)

            await asyncio.gather(*[_search(item["id"]) for item in media_items])

        logger.debug("search queued for %d items in %s", len(media_items), self.app_name)
