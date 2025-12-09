"""Transforms RoyaleAPI payloads into PlayerData objects."""

from __future__ import annotations

from typing import Any, Dict, List

from .constants import CARD_LEVEL_CAP, CARD_RARITIES, CARD_RARITY_START_LEVELS
from .game_data import GameData
from .models import Card, Inventory, PlayerData, PlayerProfile


def player_data_from_snapshot(snapshot: Dict[str, Any], gold: int, gems: int) -> PlayerData:
    game_data = GameData()

    try:
        king_level = int(snapshot.get("expLevel"))
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("RoyaleAPI snapshot is missing the 'expLevel' field") from exc

    king_cap = game_data.king_levels[-1]["level"]
    king_level = max(1, min(king_level, king_cap))

    try:
        xp_into_level = int(snapshot.get("expPoints") or 0)
    except (TypeError, ValueError):
        xp_into_level = 0

    xp_row = next((row for row in game_data.king_levels if row["level"] == king_level), None)
    xp_to_next = xp_row.get("xp_to_next") if xp_row else 0
    xp_into_level = max(0, min(xp_into_level, xp_to_next or 0))

    profile = PlayerProfile(king_level=king_level, xp_into_level=xp_into_level)

    cards: List[Card] = []
    for entry in snapshot.get("cards", []):
        name = entry.get("name")
        rarity = entry.get("rarity")
        level = entry.get("level")
        if not name or rarity is None or level is None:
            continue

        normalized_rarity = game_data.normalize_rarity(str(rarity))
        try:
            parsed_level = int(level)
        except (TypeError, ValueError):
            continue

        offset = CARD_RARITY_START_LEVELS.get(normalized_rarity, 1) - 1
        parsed_level = parsed_level + offset
        parsed_level = max(1, min(parsed_level, CARD_LEVEL_CAP))

        count_raw = entry.get("count", 0)
        try:
            count_value = max(0, int(count_raw))
        except (TypeError, ValueError):
            count_value = 0

        cards.append(
            Card(
                name=name,
                rarity=normalized_rarity,
                level=parsed_level,
                count=count_value,
            )
        )

    if not cards:
        raise ValueError("RoyaleAPI snapshot did not include any cards to optimize")

    inventory = Inventory(
        gold=gold,
        gems=gems,
        wild_cards={rarity: 0 for rarity in CARD_RARITIES},
    )

    return PlayerData(profile=profile, inventory=inventory, cards=cards)
