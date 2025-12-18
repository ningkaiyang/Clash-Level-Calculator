"""Minimal Flask frontend for the Clash Level Calculator."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from flask import Flask, render_template, request
from pydantic import ValidationError

from .api_adapter import player_data_from_snapshot
from .clients import RoyaleAPIClient, RoyaleAPIError
from .constants import IMPORTANT_KING_LEVELS
from .models import OptimizationMode, OptimizationResult, OptimizationSettings, PlayerData
from .optimizer import Level16Optimizer, find_min_gem_path, find_min_gold_path


load_dotenv()


# JSON sample and paste support have been removed; this web app only supports RoyaleAPI fetches.


def _parse_settings(form_data: Dict[str, str]) -> OptimizationSettings:
    def _flag(key: str) -> bool:
        return form_data.get(key) == "on"
    return OptimizationSettings(
        use_gems=_flag("use_gems"),
        infinite_gold=_flag("infinite_gold"),
    )


def _parse_mode(form_data: Dict[str, str]) -> OptimizationMode:
    """Parse the optimization mode from form data."""
    mode_value = form_data.get("mode", "min_cost")
    if mode_value == "max_xp":
        return OptimizationMode.MAX_XP_FROM_RESOURCES
    return OptimizationMode.MIN_COST_TO_NEXT_KING  # Default


def _get_next_important_king_level(current_level: int) -> int:
    """Get the next important king level milestone."""
    for milestone in IMPORTANT_KING_LEVELS:
        if milestone > current_level:
            return milestone
    # If past all milestones, just return next level
    return current_level + 1


def _parse_target_level(form_data: Dict[str, str], current_king_level: int) -> int:
    """Parse the target king level from form data, defaulting to next important level."""
    target_str = form_data.get("target_level", "").strip()
    if target_str:
        try:
            target = int(target_str)
            if target > current_king_level:
                return target
        except ValueError:
            pass
    # Default to next important king level
    return _get_next_important_king_level(current_king_level)


# JSON paste support removed: web UI only allows RoyaleAPI lookup for live data


def _player_data_from_api(
    form_data: Dict[str, str],
    gold: int,
    gems: int,
    wild_cards: Dict[str, int],
) -> PlayerData:
    tag = (form_data.get("player_tag") or "").strip().upper()
    if not tag:
        raise ValueError("Player tag is required when using RoyaleAPI.")

    client = RoyaleAPIClient()
    snapshot = client.fetch_player_snapshot(tag)
    return player_data_from_snapshot(snapshot, gold=gold, gems=gems, wild_cards=wild_cards)


def _run_min_cost_optimizer(
    player_data: PlayerData,
    target_level: int,
    minimize_gold: bool = False,
) -> OptimizationResult:
    """Run the min cost optimizer with either gold or gem minimization."""
    if minimize_gold:
        return find_min_gold_path(player_data, target_level)
    else:
        return find_min_gem_path(player_data, target_level)


def _run_max_xp_optimizer(
    player_data: PlayerData,
    settings: OptimizationSettings,
) -> OptimizationResult:
    """Run the max XP optimizer."""
    optimizer = Level16Optimizer(player_data, settings=settings)
    return optimizer.generate_plan()


def _default_settings() -> OptimizationSettings:
    return OptimizationSettings(use_gems=False, infinite_gold=False)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")


@app.route("/", methods=["GET", "POST"])
def index():  # type: ignore[override]
    errors: list[str] = []
    result: OptimizationResult | None = None

    player_tag = request.form.get("player_tag", "")
    gold_input = request.form.get("gold", "")
    gems_input = request.form.get("gems", "")
    wild_cards_input = {k: "" for k in ["common", "rare", "epic", "legendary", "champion"]}
    settings = _default_settings()
    mode = OptimizationMode.MIN_COST_TO_NEXT_KING  # Default mode
    target_level_input = request.form.get("target_level", "")
    current_king_level = 1
    next_important_level = _get_next_important_king_level(current_king_level)
    player_data: PlayerData | None = None
    minimize_gold = False  # Default: minimize gems

    if request.method == "POST":
        settings = _parse_settings(request.form)
        mode = _parse_mode(request.form)
        minimize_gold = request.form.get("minimize_gold") == "on"
        wild_cards_input = {
            "common": request.form.get("wild_common", ""),
            "rare": request.form.get("wild_rare", ""),
            "epic": request.form.get("wild_epic", ""),
            "legendary": request.form.get("wild_legendary", ""),
            "champion": request.form.get("wild_champion", ""),
        }
        try:
            gold = int(gold_input.replace(",", "")) if gold_input.strip() else 0
            gems = int(gems_input.replace(",", "")) if gems_input.strip() else 0
            wild_cards_values: Dict[str, int] = {}
            for key, value in wild_cards_input.items():
                try:
                    wild_cards_values[key.capitalize()] = int(value.replace(",", "")) if value.strip() else 0
                except ValueError:
                    wild_cards_values[key.capitalize()] = 0

            player_data = _player_data_from_api(request.form, gold, gems, wild_cards_values)
            current_king_level = player_data.profile.king_level
            next_important_level = _get_next_important_king_level(current_king_level)
            
            if mode == OptimizationMode.MIN_COST_TO_NEXT_KING:
                # Parse target level for min cost mode
                target_level = _parse_target_level(request.form, current_king_level)
                result = _run_min_cost_optimizer(player_data, target_level, minimize_gold)
            else:
                # Max XP mode uses user-provided gold/gems
                result = _run_max_xp_optimizer(player_data, settings)
                # Autofill inputs with parsed values
                gold_input = str(gold)
                gems_input = str(gems)
        except (ValueError, ValidationError, RoyaleAPIError) as exc:
            errors.append(str(exc))

    return render_template(
        "index.html",
        player_tag=player_tag,
        gold_input=gold_input,
        gems_input=gems_input,
        wild_cards_input=wild_cards_input,
        settings=settings,
        errors=errors,
        result=result,
        mode=mode.value,
        target_level_input=target_level_input,
        current_king_level=current_king_level,
        next_important_level=next_important_level,
        important_king_levels=IMPORTANT_KING_LEVELS,
        player_data=player_data,
        minimize_gold=minimize_gold,
    )


@app.route("/health")
def health():
    # Simple health check for Render or other load balancers
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "4000")), debug=True)
