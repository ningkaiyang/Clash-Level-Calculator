"""Implementation of the Level 16 XP optimization algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .constants import CARD_RARITIES
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
        self._gold_spent = 0
        self._xp_total = (
            self.game_data.total_xp_for_level(player_data.profile.king_level)
            + player_data.profile.xp_into_level
        )

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
            total_gold_spent=self._gold_spent,
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
            gold_cost=gold_cost,
            cards_required=cards_required,
            cards_used=cards_used,
            wild_cards_used=wild_used,
            gems_used=gems_used,
            xp_gained=xp_gain,
            efficiency_ratio=efficiency_ratio,
            material_efficiency=material_efficiency,
        )

    def _available_wild(self, rarity: str) -> int:
        return max(0, self.inventory.wild_cards.get(rarity, 0))

    def _calculate_efficiency(
        self,
        target_level: int,
        gold_cost: int,
        xp_gain: int,
        cards_required: int,
        gems_used: int,
    ) -> float:
        override = self.game_data.get_efficiency_override(target_level)
        if override is not None:
            return override

        denominator = xp_gain or 1
        # Gems are a separate currency and not converted to gold; do not penalize gem usage scaled with gold, just in general.
        return (gold_cost + gems_used) / denominator

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
        self._gold_spent += candidate.gold_cost

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


def find_min_gem_path(
    player_data: PlayerData,
    target_king_level: int,
    game_data: Optional[GameData] = None,
) -> OptimizationResult:
    """
    Find the upgrade path that uses the minimum number of gems to reach the target king level.
    
    Uses an iterative approach: start with unlimited gems, then try with (gems_used - 1)
    repeatedly until we can no longer reach the target level.
    """
    gd = game_data or GameData()
    
    # Start with a very high gem limit (effectively unlimited)
    current_gem_limit = 10_000_000
    best_result: Optional[OptimizationResult] = None
    
    while True:
        # Create settings with current gem limit
        settings = OptimizationSettings(use_gems=True, infinite_gold=True)
        
        # Create player data copy with current gem limit
        player_copy = player_data.model_copy(deep=True)
        player_copy.inventory.gems = current_gem_limit
        
        optimizer = MinCostToKingLevelOptimizer(
            player_copy,
            settings=settings,
            game_data=gd,
            target_king_level=target_king_level,
        )
        result = optimizer.generate_plan()
        
        # Check if we reached the target
        if result.final_profile.king_level >= target_king_level:
            best_result = result
            
            # If no gems used, we found the minimum (0)
            if result.total_gems_used == 0:
                break
            
            # Try with one fewer gem
            current_gem_limit = result.total_gems_used - 1
        else:
            # Could not reach target with this gem limit, previous result was the minimum
            break
    
    # If we never found a valid path, return an empty result
    if best_result is None:
        final_profile = gd.king_progress_from_total_xp(
            gd.total_xp_for_level(player_data.profile.king_level)
            + player_data.profile.xp_into_level
        )
        return OptimizationResult(
            actions=[],
            total_xp_gained=0,
            final_profile=PlayerProfile(
                king_level=final_profile.level,
                xp_into_level=final_profile.xp_into_level,
            ),
            final_gold=player_data.inventory.gold,
            final_gems=player_data.inventory.gems,
            total_gold_spent=0,
            total_wild_cards_used={rarity: 0 for rarity in CARD_RARITIES},
            total_gems_used=0,
        )
    
    return best_result


def find_min_gold_path(
    player_data: PlayerData,
    target_king_level: int,
    game_data: Optional[GameData] = None,
) -> OptimizationResult:
    """
    Find the upgrade path that uses the minimum amount of gold to reach the target king level.
    
    Uses an iterative approach: start with unlimited gold, then try with (gold_spent - 1)
    repeatedly until we can no longer reach the target level.
    This may use more gems to compensate for less gold.
    """
    gd = game_data or GameData()
    
    # Start with a very high gold limit (effectively unlimited)
    current_gold_limit = 100_000_000
    best_result: Optional[OptimizationResult] = None
    
    while True:
        # Create settings with gems allowed and current gold limit
        settings = OptimizationSettings(use_gems=True, infinite_gold=False)
        
        # Create player data copy with current gold limit and unlimited gems
        player_copy = player_data.model_copy(deep=True)
        player_copy.inventory.gold = current_gold_limit
        player_copy.inventory.gems = 10_000_000  # Unlimited gems
        
        optimizer = MinCostToKingLevelOptimizer(
            player_copy,
            settings=settings,
            game_data=gd,
            target_king_level=target_king_level,
        )
        result = optimizer.generate_plan()
        
        # Check if we reached the target
        if result.final_profile.king_level >= target_king_level:
            best_result = result
            
            # If no gold used, we found the minimum (0)
            if result.total_gold_spent == 0:
                break
            
            # Try with one fewer gold
            current_gold_limit = result.total_gold_spent - 1
        else:
            # Could not reach target with this gold limit, previous result was the minimum
            break
    
    # If we never found a valid path, return an empty result
    if best_result is None:
        final_profile = gd.king_progress_from_total_xp(
            gd.total_xp_for_level(player_data.profile.king_level)
            + player_data.profile.xp_into_level
        )
        return OptimizationResult(
            actions=[],
            total_xp_gained=0,
            final_profile=PlayerProfile(
                king_level=final_profile.level,
                xp_into_level=final_profile.xp_into_level,
            ),
            final_gold=player_data.inventory.gold,
            final_gems=player_data.inventory.gems,
            total_gold_spent=0,
            total_wild_cards_used={rarity: 0 for rarity in CARD_RARITIES},
            total_gems_used=0,
        )
    
    return best_result


class MinCostToKingLevelOptimizer:
    """
    Optimizer that finds the minimum-cost path to reach the next king level.
    
    Allows overshoot if a single cheaper upgrade exceeds the XP target.
    Tie-breaks: 1) least gems, 2) least gold, 3) fewest upgrades.
    """

    def __init__(
        self,
        player_data: PlayerData,
        settings: Optional[OptimizationSettings] = None,
        game_data: Optional[GameData] = None,
        target_king_level: Optional[int] = None,
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
        self._gold_spent = 0
        
        current_total_xp = (
            self.game_data.total_xp_for_level(player_data.profile.king_level)
            + player_data.profile.xp_into_level
        )
        self._starting_xp = current_total_xp
        self._xp_total = current_total_xp

        # Determine target king level (next level by default)
        if target_king_level is not None:
            self._target_level = target_king_level
        else:
            self._target_level = player_data.profile.king_level + 1
        
        # Calculate XP needed to reach target
        self._target_xp = self.game_data.total_xp_for_level(self._target_level)
        self._xp_needed = max(0, self._target_xp - current_total_xp)

        self._wild_usage: Dict[str, int] = {rarity: 0 for rarity in CARD_RARITIES}
        self._total_gems_used = 0

    def generate_plan(self) -> OptimizationResult:
        """
        Generate the minimum-cost upgrade plan to reach the target king level.
        
        Uses a greedy approach that prioritizes upgrades by cost efficiency
        (cost per XP), with tie-breaks on gems, gold, then action count.
        """
        if self._xp_needed <= 0:
            # Already at or past target level
            final_profile = self.game_data.king_progress_from_total_xp(self._xp_total)
            return OptimizationResult(
                actions=[],
                total_xp_gained=0,
                final_profile=PlayerProfile(
                    king_level=final_profile.level,
                    xp_into_level=final_profile.xp_into_level,
                ),
                final_gold=self.inventory.gold,
                final_gems=self.inventory.gems,
                total_gold_spent=0,
                total_wild_cards_used=self._wild_usage,
                total_gems_used=0,
            )

        # Greedy selection: pick cheapest upgrade per XP until we reach target
        while self._xp_total < self._target_xp:
            candidate = self._select_best_candidate()
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
            total_gold_spent=self._gold_spent,
            total_wild_cards_used=self._wild_usage,
            total_gems_used=self._total_gems_used,
        )

    def _select_best_candidate(self) -> Optional[UpgradeCandidate]:
        """
        Select the best upgrade candidate based on cost efficiency.
        
        Priority: lowest total cost (gold + gems) per XP gained.
        Tie-breaks: 1) least gems, 2) least gold, 3) higher XP (fewer operations).
        """
        best: Optional[UpgradeCandidate] = None
        for index, card in enumerate(self.cards):
            candidate = self._build_candidate(index, card)
            if candidate is None:
                continue
            if best is None:
                best = candidate
                continue
            
            # Compare by cost efficiency (cost per XP)
            if candidate.efficiency_ratio < best.efficiency_ratio:
                best = candidate
            elif candidate.efficiency_ratio == best.efficiency_ratio:
                # Tie-break 1: prefer fewer gems
                if candidate.gems_used < best.gems_used:
                    best = candidate
                elif candidate.gems_used == best.gems_used:
                    # Tie-break 2: prefer less gold
                    if candidate.gold_cost < best.gold_cost:
                        best = candidate
                    elif candidate.gold_cost == best.gold_cost:
                        # Tie-break 3: prefer higher XP (fewer total operations)
                        if candidate.xp_gained > best.xp_gained:
                            best = candidate
        return best

    def _build_candidate(self, index: int, card: Card) -> Optional[UpgradeCandidate]:
        """Build an upgrade candidate for a card if affordable."""
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

        # Cost efficiency: total cost per XP (for minimization)
        efficiency_ratio = self._calculate_cost_efficiency(gold_cost, gems_used, xp_gain)
        material_efficiency = xp_gain / cards_required if cards_required else 0

        return UpgradeCandidate(
            index=index,
            card=card,
            from_level=card.level,
            to_level=next_level,
            gold_cost=gold_cost,
            cards_required=cards_required,
            cards_used=cards_used,
            wild_cards_used=wild_used,
            gems_used=gems_used,
            xp_gained=xp_gain,
            efficiency_ratio=efficiency_ratio,
            material_efficiency=material_efficiency,
        )

    def _available_wild(self, rarity: str) -> int:
        """All wild cards are available (no buffer)."""
        return max(0, self.inventory.wild_cards.get(rarity, 0))

    def _calculate_cost_efficiency(self, gold_cost: int, gems_used: int, xp_gain: int) -> float:
        """
        Calculate cost efficiency for minimization mode.
        
        Returns total cost (gold + gems) per XP gained.
        Lower is better for cost minimization.
        """
        denominator = xp_gain or 1
        # For minimization, we want raw cost per XP without overrides
        return (gold_cost + gems_used) / denominator

    def _commit_candidate(self, candidate: UpgradeCandidate) -> None:
        """Apply the upgrade to the state."""
        card = self.cards[candidate.index]
        card.count -= candidate.cards_used
        card.level = candidate.to_level

        if not self.settings.infinite_gold:
            self.inventory.gold -= candidate.gold_cost
        self.inventory.gems -= candidate.gems_used
        self.inventory.wild_cards[card.rarity] -= candidate.wild_cards_used
        self._wild_usage[card.rarity] += candidate.wild_cards_used
        self._total_gems_used += candidate.gems_used
        self._gold_spent += candidate.gold_cost

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
