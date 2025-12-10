"""Minimal Flask frontend for the Clash Level Calculator."""

from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask, render_template, request
from pydantic import ValidationError

from .api_adapter import player_data_from_snapshot
from .clients import RoyaleAPIClient, RoyaleAPIError
from .models import OptimizationResult, OptimizationSettings, PlayerData
from .optimizer import Level16Optimizer


load_dotenv()


# JSON sample and paste support have been removed; this web app only supports RoyaleAPI fetches.


def _parse_settings(form_data: Dict[str, str]) -> OptimizationSettings:
    def _flag(key: str) -> bool:
        return form_data.get(key) == "on"
    return OptimizationSettings(
        use_gems=_flag("use_gems"),
        infinite_gold=_flag("infinite_gold"),
        # Buffer disabled so user-entered Wild Cards are used as-is.
        keep_wild_card_buffer=False,
    )


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


def _run_optimizer(player_data: PlayerData, settings: OptimizationSettings) -> OptimizationResult:
    optimizer = Level16Optimizer(player_data, settings=settings)
    return optimizer.generate_plan()


def _default_settings() -> OptimizationSettings:
    return OptimizationSettings(use_gems=False, infinite_gold=False, keep_wild_card_buffer=False)


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
    source = "api"
    settings = _default_settings()

    if request.method == "POST":
        settings = _parse_settings(request.form)
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

            result = _run_optimizer(player_data, settings)
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
    )


@app.route("/health")
def health():
    # Simple health check for Render or other load balancers
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "4000")), debug=True)
