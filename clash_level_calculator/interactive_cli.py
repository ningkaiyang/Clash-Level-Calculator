"""Interactive CLI that fetches player data from RoyaleAPI and plans upgrades."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv

from .api_adapter import player_data_from_snapshot
from .clients import RoyaleAPIClient, RoyaleAPIError
from .models import OptimizationResult, OptimizationSettings, PlayerData
from .optimizer import Level16Optimizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive Clash Level Calculator powered by RoyaleAPI")
    parser.add_argument(
        "--offline-file",
        type=Path,
        help="Optional path to a saved RoyaleAPI JSON response for offline testing",
    )
    parser.add_argument("--player-tag", type=str, help="Prefill the player tag instead of prompting")
    parser.add_argument("--gold", type=int, help="Prefill the available gold instead of prompting")
    parser.add_argument("--gems", type=int, help="Prefill the available gems instead of prompting")
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write the combined scenario output (text file)",
    )
    return parser.parse_args()


def prompt_text(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{message}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default


def prompt_int(message: str, default: int | None = None) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{message}{suffix}: ").replace(",", "").strip()
        if not raw:
            if default is not None:
                return default
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number (e.g., 450000).")


def load_snapshot(args: argparse.Namespace, player_tag: str, client: RoyaleAPIClient) -> dict:
    if args.offline_file:
        with Path(args.offline_file).expanduser().open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return client.fetch_player_snapshot(player_tag)


def run_scenarios(player_data: PlayerData) -> List[Tuple[str, OptimizationResult]]:
    scenarios: List[Tuple[str, OptimizationSettings]] = [
        (
            "All Resources (Gold + Gems + Cards) - Note: Gem Costs Are Estimates!",
            OptimizationSettings(use_gems=True, keep_wild_card_buffer=False),
        ),
        (
            "Gold + Cards Only",
            OptimizationSettings(use_gems=False, keep_wild_card_buffer=False),
        ),
        (
            "Card Bottleneck (Infinite Gold)",
            OptimizationSettings(use_gems=False, infinite_gold=True, keep_wild_card_buffer=False),
        ),
    ]

    outputs: List[Tuple[str, OptimizationResult]] = []
    for title, settings in scenarios:
        optimizer = Level16Optimizer(player_data.model_copy(deep=True), settings=settings)
        result = optimizer.generate_plan()
        outputs.append((title, result))
    return outputs


def format_result(title: str, result: OptimizationResult) -> str:
    lines = [f"=== {title} ==="]
    lines.append(
        f"Projected King Level: {result.final_profile.king_level} (+{result.final_profile.xp_into_level:,} XP into level)"
    )
    lines.append(f"Upgrades planned: {len(result.actions)}")
    lines.append(f"Total XP gained: {result.total_xp_gained:,}")
    lines.append(f"Gold spent: {result.total_gold_spent:,}")
    lines.append(f"Gems spent: {result.total_gems_used:,}")
    if result.actions:
        lines.append("-- Upgrade Path --")
        for action in result.actions:
            lines.append(
                f"{action.card_name}: {action.from_level}->{action.to_level} | "
                f"Gold {action.gold_cost:,} | Cards {action.card_cost:,} | "
                f"Gems {action.gems_used:,} | XP +{action.xp_gained:,} | Ratio {action.efficiency_ratio:.2f}"
            )
    else:
        lines.append("No upgrades available for this scenario.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    args = parse_args()

    player_tag = args.player_tag or prompt_text("Enter player tag (include or omit #)").upper()
    gold = args.gold if args.gold is not None else prompt_int("Enter available Gold")
    gems = args.gems if args.gems is not None else prompt_int("Enter available Gems")

    client = RoyaleAPIClient()
    try:
        snapshot = load_snapshot(args, player_tag, client)
    except RoyaleAPIError as error:
        print(f"RoyaleAPI request failed: {error}")
        return

    player_data = player_data_from_snapshot(snapshot, gold=gold, gems=gems)

    print("\nNote: Wild Cards are ignored in this interactive workflow.\n")

    scenario_results = run_scenarios(player_data)
    combined_output = "\n".join(format_result(title, result) for title, result in scenario_results)
    print(combined_output)

    if args.report:
        report_path = Path(args.report)
        report_path.write_text(combined_output, encoding="utf-8")
        print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
