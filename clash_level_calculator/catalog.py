"""Card catalog helper backed by RoyaleAPI's open data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import requests


class CardCatalog:
    """Provides metadata lookups for cards using RoyaleAPI's dataset."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "cards.json"
        
        # Try to fetch live data from RoyaleAPI
        live_url = "https://royaleapi.github.io/cr-api-data/json/cards.json"
        try:
            response = requests.get(live_url, timeout=10)
            response.raise_for_status()
            self.cards = response.json()
        except (requests.RequestException, ValueError):
            # Fallback to local data if fetch fails
            with data_path.open("r", encoding="utf-8") as source:
                self.cards = json.load(source)

        self._by_name = {entry["name"].lower(): entry for entry in self.cards}
        self._by_key = {entry["key"].lower(): entry for entry in self.cards}

    def find(self, identifier: str) -> Optional[Dict[str, object]]:
        token = identifier.strip().lower()
        return self._by_name.get(token) or self._by_key.get(token)

    def get_rarity(self, identifier: str) -> Optional[str]:
        entry = self.find(identifier)
        return entry.get("rarity") if entry else None

    def require(self, identifier: str) -> Dict[str, object]:
        entry = self.find(identifier)
        if entry is None:
            raise KeyError(f"Card '{identifier}' is not present in the RoyaleAPI card dataset")
        return entry
