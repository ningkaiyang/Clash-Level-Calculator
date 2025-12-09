"""Helper utilities to read the static economy tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .constants import (
    CARD_MATERIAL_REQUIREMENTS,
    CARD_RARITIES,
    CARD_XP_TABLE,
    EFFICIENCY_OVERRIDES,
    GEM_CARD_VALUES,
    GOLD_COST_TABLE,
    KING_XP_TABLE,
)


@dataclass
class KingLevelProgress:
    level: int
    xp_into_level: int
    xp_to_next: int
    total_xp: int

    @property
    def next_level(self) -> Optional[int]:
        return None if self.xp_to_next == 0 else self.level + 1


class GameData:
    """Central access point for deterministic Clash Royale economy tables."""

    def __init__(self) -> None:
        self.material_requirements = CARD_MATERIAL_REQUIREMENTS
        self.gold_costs = GOLD_COST_TABLE
        self.xp_rewards = CARD_XP_TABLE
        self.gem_values = GEM_CARD_VALUES
        self.efficiency_overrides = EFFICIENCY_OVERRIDES
        self.king_levels = KING_XP_TABLE
        self._cumulative_lookup = {
            row["level"]: row["cumulative"] for row in self.king_levels if row["cumulative"] is not None
        }

    def get_material_requirement(self, rarity: str, target_level: int) -> Optional[int]:
        return self.material_requirements.get(rarity, {}).get(target_level)

    def get_gold_cost(self, target_level: int) -> Optional[int]:
        return self.gold_costs.get(target_level)

    def get_xp_reward(self, target_level: int) -> Optional[int]:
        return self.xp_rewards.get(target_level)

    def get_efficiency_override(self, target_level: int) -> Optional[float]:
        return self.efficiency_overrides.get(target_level)

    def gem_value_for_rarity(self, rarity: str) -> float:
        return self.gem_values.get(rarity, 0.0)

    def total_xp_for_level(self, level: int) -> int:
        max_level = self.king_levels[-1]["level"]
        level = max(1, min(level, max_level))
        return self._cumulative_lookup.get(level, 0)

    def king_progress_from_total_xp(self, total_xp: int) -> KingLevelProgress:
        current_row = self.king_levels[0]
        for row in self.king_levels:
            if total_xp >= row["cumulative"]:
                current_row = row
            else:
                break

        xp_to_next = current_row["xp_to_next"] or 0
        level = current_row["level"]
        xp_into_level = total_xp - (current_row["cumulative"] or 0)
        if xp_to_next:
            xp_into_level = min(xp_into_level, xp_to_next)
        else:
            xp_into_level = 0

        return KingLevelProgress(
            level=level,
            xp_into_level=xp_into_level,
            xp_to_next=xp_to_next,
            total_xp=total_xp,
        )

    def normalize_rarity(self, rarity: str) -> str:
        canonical = rarity.capitalize()
        if canonical not in CARD_RARITIES:
            raise ValueError(f"Unknown rarity '{rarity}'")
        return canonical
