"""Placeholder RoyaleAPI client for future integration."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class RoyaleAPIClient:
    """Lightweight wrapper that will call the Clash Royale API once a key is provided."""

    BASE_URL = "https://api.clashroyale.com/v1"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("ROYALE_API_KEY")

    def fetch_player_snapshot(self, player_tag: str) -> Dict[str, Any]:
        """Fetch live player data once API wiring is complete."""

        raise NotImplementedError(
            "API integration is not implemented yet. Supply a Developer Key and add HTTP wiring here."
        )
