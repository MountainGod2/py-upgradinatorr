"""Starr application API client."""

import asyncio
from typing import Any, Optional, cast

import aiohttp
from rich.console import Console

console = Console()


class StarrAPIError(Exception):
    """Raised when Starr API returns an error."""

    def __init__(self, status: int, message: str, application: str) -> None:
        self.status = status
        self.message = message
        self.application = application
        super().__init__(f"{application} responded with {status}: {message}")


class StarrClient:
    """Async client for interacting with Starr application APIs."""

    ENDPOINTS = {
        "radarr": "movie",
        "sonarr": "series",
        "lidarr": "artist",
        "readarr": "author",
    }

    SEARCH_COMMANDS = {
        "radarr": "MoviesSearch",
        "sonarr": "SeriesSearch",
        "lidarr": "ArtistSearch",
        "readarr": "AuthorSearch",
    }

    EDITOR_ENDPOINTS = {
        "radarr": ("movie/editor", "movieIds"),
        "sonarr": ("series/editor", "seriesIds"),
        "lidarr": ("artist/editor", "artistIds"),
        "readarr": ("author/editor", "authorIds"),
    }

    def __init__(self, app_name: str, url: str, api_key: str) -> None:
        """Initialize Starr client.

        Args:
            app_name: Name of the application (radarr, sonarr, lidarr, readarr)
            url: Base URL of the application
            api_key: API key for authentication
        """
        self.app_name = app_name.lower()
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.api_version: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "StarrClient":
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"}
        )
        self.api_version = await self._get_api_version()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
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
            raise RuntimeError("Client not initialized. Use async with statement.")

        url = f"{self.base_url}/api/{self.api_version}/{endpoint}"

        async with self._session.request(method, url, **kwargs) as response:
            if response.status >= 400:
                error_messages = {
                    302: "Redirect - Are you missing the URL base?",
                    400: "Bad Request - Please check your configuration",
                    401: "Unauthorized - Please check your API key",
                    404: "Not Found - Please check your configuration",
                    409: "Conflict - Please check your configuration",
                    500: "Internal Server Error - Please check your configuration",
                }

                message = error_messages.get(
                    response.status, f"Unexpected status code {response.status}"
                )
                raise StarrAPIError(response.status, message, self.app_name)

            return cast(dict[str, Any] | list[dict[str, Any]], await response.json())

    async def _get_api_version(self) -> str:
        """Get current API version from application."""
        if not self._session:
            raise RuntimeError("Client not initialized")

        url = f"{self.base_url}/api"
        async with self._session.get(url) as response:
            if response.status != 200:
                raise StarrAPIError(
                    response.status,
                    "Failed to get API version",
                    self.app_name,
                )
            data = await response.json()
            return cast(str, data["current"])

    async def get_all_media(self) -> list[dict[str, Any]]:
        """Get all media items from the application."""
        endpoint = self.ENDPOINTS[self.app_name]
        media = await self._request("GET", endpoint)
        return media if isinstance(media, list) else []

    async def get_tag(self, tag_name: str) -> Optional[dict[str, Any]]:
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

        raise ValueError(f"Quality profile '{profile_name}' not found in {self.app_name.title()}")

    async def add_tags_to_media(self, media_ids: list[int], tag_id: int) -> None:
        """Add tag to multiple media items."""
        endpoint, id_key = self.EDITOR_ENDPOINTS[self.app_name]

        body = {id_key: media_ids, "tags": [tag_id], "applyTags": "add"}

        await self._request("PUT", endpoint, json=body)

    async def remove_tags_from_media(self, media_ids: list[int], tag_id: int) -> None:
        """Remove tag from multiple media items."""
        endpoint, id_key = self.EDITOR_ENDPOINTS[self.app_name]

        body = {id_key: media_ids, "tags": [tag_id], "applyTags": "remove"}

        await self._request("PUT", endpoint, json=body)

    async def search_media(self, media_id: int) -> None:
        """Trigger search for a single media item."""
        command = self.SEARCH_COMMANDS[self.app_name]

        # Build the appropriate body based on app type
        if self.app_name == "radarr":
            body: dict[str, Any] = {"name": command, "movieIds": [media_id]}
        else:
            # Sonarr, Lidarr, Readarr use singular ID
            object_name = self.ENDPOINTS[self.app_name]
            id_field = f"{object_name}Id"
            body = {"name": command, id_field: media_id}

        await self._request("POST", "command", json=body)

    async def search_media_batch(self, media_items: list[dict[str, Any]]) -> None:
        """Search for multiple media items."""
        # Radarr supports batch search, others need individual searches
        if self.app_name == "radarr":
            media_ids = [item["id"] for item in media_items]
            body = {"name": "MoviesSearch", "movieIds": media_ids}
            await self._request("POST", "command", json=body)
        else:
            # Search one at a time for Sonarr/Lidarr/Readarr
            # Use a semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(10)

            async def logged_search(media_id: int) -> None:
                async with semaphore:
                    await self.search_media(media_id)

            tasks = [logged_search(item["id"]) for item in media_items]
            await asyncio.gather(*tasks)

        console.log(
            f"[cyan]Started search for {len(media_items)} media items in "
            f"{self.app_name.title()}[/cyan]"
        )
