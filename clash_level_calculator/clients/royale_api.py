"""RoyaleAPI client implementation ready for developer-key usage."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


class RoyaleAPIError(RuntimeError):
    """Raised when the RoyaleAPI endpoint rejects a request."""


class RoyaleAPIClient:
    """Minimal wrapper around the Clash Royale API.

    Defaults to the RoyaleAPI proxy so outbound requests originate from a
    whitelisted static IP (45.79.218.79). Override with ROYALE_API_BASE_URL
    or the base_url constructor arg to target the official API directly.
    """

    BASE_URL = "https://proxy.royaleapi.dev/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ROYALE_API_KEY")
        self.base_url = base_url or os.getenv("ROYALE_API_BASE_URL") or self.BASE_URL
        self.session = session or requests.Session()

    def fetch_player_snapshot(self, player_tag: str) -> Dict[str, Any]:
        if not player_tag:
            raise ValueError("player_tag is required")

        if not self.api_key:
            raise RoyaleAPIError(
                "Missing API key. Set the ROYALE_API_KEY environment variable or pass api_key explicitly."
            )

        normalized_tag = player_tag.strip().upper()
        if not normalized_tag.startswith("#"):
            normalized_tag = f"#{normalized_tag}"

        encoded_tag = quote(normalized_tag, safe="")
        url = f"{self.base_url}/players/{encoded_tag}"
        response = self.session.get(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            timeout=15,
        )

        if response.status_code == 404:
            raise RoyaleAPIError(f"Player {normalized_tag} was not found. Double-check the tag.")
        if response.status_code == 403:
            raise RoyaleAPIError(
                "Access to RoyaleAPI was denied. Verify that your Developer Key is valid and whitelisted for IP 45.79.218.79."
            )
        if not response.ok:
            raise RoyaleAPIError(
                f"RoyaleAPI request failed with status {response.status_code}: {response.text.strip()}"
            )

        return response.json()

