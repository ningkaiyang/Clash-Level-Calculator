"""Pydantic models describing the player's state and optimizer outputs."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class OptimizationMode(str, Enum):
    """Optimization mode selection."""
    MIN_COST_TO_NEXT_KING = "min_cost"  # Minimize resources to reach next king level
    MAX_XP_FROM_RESOURCES = "max_xp"    # Maximize XP from current resources


class Card(BaseModel):
    name: str
    rarity: str
    level: int = Field(ge=1, le=16)
    count: int = Field(ge=0)

    def next_level(self) -> Optional[int]:
        return None if self.level >= 16 else self.level + 1


class Inventory(BaseModel):
    gold: int = 0
    gems: int = 0
    wild_cards: Dict[str, int] = Field(default_factory=dict)


class PlayerProfile(BaseModel):
    king_level: int = Field(ge=1)
    xp_into_level: int = Field(ge=0)


class PlayerData(BaseModel):
    profile: PlayerProfile
    inventory: Inventory
    cards: List[Card]


class OptimizationSettings(BaseModel):
    use_gems: bool = False
    infinite_gold: bool = False


class UpgradeAction(BaseModel):
    card_name: str
    rarity: str
    from_level: int
    to_level: int
    gold_cost: int
    card_cost: int
    wild_cards_used: int
    gems_used: int
    xp_gained: int
    efficiency_ratio: float
    material_efficiency: float


class OptimizationResult(BaseModel):
    actions: List[UpgradeAction]
    total_xp_gained: int
    final_profile: PlayerProfile
    final_gold: int
    final_gems: int
    total_gold_spent: int
    total_wild_cards_used: Dict[str, int]
    total_gems_used: int
