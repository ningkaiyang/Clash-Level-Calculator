"""Command-line entry point for the Clash Level Calculator."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import CardCatalog
from .models import OptimizationSettings
from .optimizer import Level16Optimizer
from .player_loader import load_player_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize Clash Royale upgrades for XP efficiency")
    parser.add_argument("--player-data", type=Path, required=True, help="Path to the player data JSON file")
    parser.add_argument("--use-gems", action="store_true", help="Allow the optimizer to spend gems on missing cards")
    parser.add_argument(
        "--infinite-gold",
        action="store_true",
        help="Ignore gold costs and maximize XP per card (materials bottleneck mode)",
    )
    parser.add_argument(
        "--gem-gold-ratio",
        type=float,
        default=125.0,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = CardCatalog()
    player_data = load_player_data(args.player_data, catalog)

    settings = OptimizationSettings(
        use_gems=args.use_gems,
        infinite_gold=args.infinite_gold,
    )

    optimizer = Level16Optimizer(player_data, settings=settings)
    result = optimizer.generate_plan()

    print("=== Clash Level Calculator ===")
    print(f"Upgrades planned: {len(result.actions)}")
    print(f"Total XP gained: {result.total_xp_gained:,}")
    print(
        "Projected King Level: "
        f"{result.final_profile.king_level} (+{result.final_profile.xp_into_level:,} XP into level)"
    )
    print(f"Gold spent: {result.total_gold_spent:,}")
    print(f"Gems spent: {result.total_gems_used:,}")
    for rarity, used in result.total_wild_cards_used.items():
        if used:
            print(f"Wild Cards spent ({rarity}): {used:,}")

    for action in result.actions:
        print(
            f"- {action.card_name}: {action.from_level}->{action.to_level} | "
            f"Gold {action.gold_cost:,} | Cards {action.card_cost:,} | "
            f"Wild {action.wild_cards_used:,} | Gems {action.gems_used:,} | "
            f"XP +{action.xp_gained:,} | Gold/XP {action.efficiency_ratio:.2f}"
        )


if __name__ == "__main__":
    main()
