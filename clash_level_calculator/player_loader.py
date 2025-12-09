"""Utilities for loading player state from local JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .catalog import CardCatalog
from .models import PlayerData


def load_player_data(path: Path, catalog: CardCatalog) -> PlayerData:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        payload: Dict[str, Any] = json.load(handle)

    for card in payload.get("cards", []):
        if "rarity" not in card or not card["rarity"]:
            metadata = catalog.require(card["name"])
            card["rarity"] = metadata["rarity"]

    return PlayerData(**payload)
