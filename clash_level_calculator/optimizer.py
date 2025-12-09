"""Implementation of the Level 16 XP optimization algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .constants import CARD_RARITIES, WILD_CARD_BUFFER_RATIO
from .game_data import GameData
from .models import (
    Card,
    Inventory,
    OptimizationResult,
    OptimizationSettings,
    PlayerData,
    PlayerProfile,
    UpgradeAction,
)


@dataclass
class UpgradeCandidate:
    index: int
    card: Card
    from_level: int
    to_level: int
    gold_cost: int
    cards_required: int
    cards_used: int
    wild_cards_used: int
    gems_used: int
    xp_gained: int
    efficiency_ratio: float
    material_efficiency: float


class Level16Optimizer:
    def __init__(
        self,
        player_data: PlayerData,
        settings: Optional[OptimizationSettings] = None,
        game_data: Optional[GameData] = None,
    ) -> None:
        self.player_data = player_data
        self.settings = settings or OptimizationSettings()
        self.game_data = game_data or GameData()

        self.inventory: Inventory = player_data.inventory.model_copy(deep=True)
        for rarity in CARD_RARITIES:
            self.inventory.wild_cards.setdefault(rarity, 0)

        self.cards: List[Card] = [card.model_copy(deep=True) for card in player_data.cards]
        self.actions: List[UpgradeAction] = []
        self._initial_gold = self.inventory.gold
        self._initial_gems = self.inventory.gems
        self._xp_total = (
            self.game_data.total_xp_for_level(player_data.profile.king_level)
            + player_data.profile.xp_into_level
        )

        self._wild_reserve = {
            rarity: int(round(self.inventory.wild_cards[rarity] * WILD_CARD_BUFFER_RATIO))
            if self.settings.keep_wild_card_buffer
            else 0
            for rarity in CARD_RARITIES
        }
        self._wild_usage: Dict[str, int] = {rarity: 0 for rarity in CARD_RARITIES}
        self._total_gems_used = 0

    def generate_plan(self) -> OptimizationResult:
        while True:
            candidate = self._select_candidate()
            if candidate is None:
                break
            self._commit_candidate(candidate)

        final_profile = self.game_data.king_progress_from_total_xp(self._xp_total)
        return OptimizationResult(
            actions=self.actions,
            total_xp_gained=sum(action.xp_gained for action in self.actions),
            final_profile=PlayerProfile(
                king_level=final_profile.level,
                xp_into_level=final_profile.xp_into_level,
            ),
            final_gold=self.inventory.gold,
            final_gems=self.inventory.gems,
            total_gold_spent=self._initial_gold - self.inventory.gold,
            total_wild_cards_used=self._wild_usage,
            total_gems_used=self._total_gems_used,
        )

    def _select_candidate(self) -> Optional[UpgradeCandidate]:
        best: Optional[UpgradeCandidate] = None
        for index, card in enumerate(self.cards):
            candidate = self._build_candidate(index, card)
            if candidate is None:
                continue
            if best is None:
                best = candidate
                continue
            if self.settings.infinite_gold:
                if candidate.material_efficiency > best.material_efficiency:
                    best = candidate
                elif candidate.material_efficiency == best.material_efficiency and candidate.xp_gained > best.xp_gained:
                    best = candidate
            else:
                if candidate.efficiency_ratio < best.efficiency_ratio:
                    best = candidate
                elif candidate.efficiency_ratio == best.efficiency_ratio and candidate.xp_gained > best.xp_gained:
                    best = candidate
        return best

    def _build_candidate(self, index: int, card: Card) -> Optional[UpgradeCandidate]:
        next_level = card.next_level()
        if next_level is None:
            return None

        cards_required = self.game_data.get_material_requirement(card.rarity, next_level)
        gold_cost = self.game_data.get_gold_cost(next_level)
        xp_gain = self.game_data.get_xp_reward(next_level)

        if cards_required is None or gold_cost is None or xp_gain is None:
            return None

        cards_used = min(card.count, cards_required)
        remaining = cards_required - cards_used

        wild_available = self._available_wild(card.rarity)
        wild_used = min(remaining, wild_available)
        remaining -= wild_used

        gems_used = 0
        if remaining > 0:
            if not self.settings.use_gems:
                return None
            gem_cost_per_card = self.game_data.gem_value_for_rarity(card.rarity)
            gems_used = int(round(remaining * gem_cost_per_card))
            remaining = 0

        if remaining > 0:
            return None

        if not self.settings.infinite_gold and gold_cost > self.inventory.gold:
            return None
        if gems_used > self.inventory.gems:
            return None

        efficiency_ratio = self._calculate_efficiency(next_level, gold_cost, xp_gain, cards_required, gems_used)
        material_efficiency = xp_gain / cards_required if cards_required else 0

        return UpgradeCandidate(
            index=index,
            card=card,
            from_level=card.level,
            to_level=next_level,
            gold_cost=0 if self.settings.infinite_gold else gold_cost,
            cards_required=cards_required,
            cards_used=cards_used,
            wild_cards_used=wild_used,
            gems_used=gems_used,
            xp_gained=xp_gain,
            efficiency_ratio=efficiency_ratio,
            material_efficiency=material_efficiency,
        )

    def _available_wild(self, rarity: str) -> int:
        reserve = self._wild_reserve.get(rarity, 0)
        return max(0, self.inventory.wild_cards.get(rarity, 0) - reserve)

    def _calculate_efficiency(
        self,
        target_level: int,
        gold_cost: int,
        xp_gain: int,
        cards_required: int,
        gems_used: int,
    ) -> float:
        override = self.game_data.get_efficiency_override(target_level)
        if override is not None and not self.settings.infinite_gold:
            return override

        if self.settings.infinite_gold:
            return cards_required / xp_gain if xp_gain else 0

        denominator = xp_gain or 1
        gem_penalty = gems_used * self.settings.gem_to_gold_ratio
        return (gold_cost + gem_penalty) / denominator

    def _commit_candidate(self, candidate: UpgradeCandidate) -> None:
        card = self.cards[candidate.index]
        card.count -= candidate.cards_used
        card.level = candidate.to_level

        if not self.settings.infinite_gold:
            self.inventory.gold -= candidate.gold_cost
        self.inventory.gems -= candidate.gems_used
        self.inventory.wild_cards[card.rarity] -= candidate.wild_cards_used
        self._wild_usage[card.rarity] += candidate.wild_cards_used
        self._total_gems_used += candidate.gems_used

        self._xp_total += candidate.xp_gained

        self.actions.append(
            UpgradeAction(
                card_name=card.name,
                rarity=card.rarity,
                from_level=candidate.from_level,
                to_level=candidate.to_level,
                gold_cost=candidate.gold_cost,
                card_cost=candidate.cards_used,
                wild_cards_used=candidate.wild_cards_used,
                gems_used=candidate.gems_used,
                xp_gained=candidate.xp_gained,
                efficiency_ratio=candidate.efficiency_ratio,
                material_efficiency=candidate.material_efficiency,
            )
        )
