"""Minimal Flask frontend for the Clash Level Calculator."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask, render_template, request
from pydantic import ValidationError

from .api_adapter import player_data_from_snapshot
from .catalog import CardCatalog
from .clients import RoyaleAPIClient, RoyaleAPIError
from .models import OptimizationResult, OptimizationSettings, PlayerData
from .optimizer import Level16Optimizer


load_dotenv()


def _sample_payload() -> str:
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_player.json"
    try:
        return sample_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "{}"


def _parse_settings(form_data: Dict[str, str]) -> OptimizationSettings:
    def _flag(key: str) -> bool:
        return form_data.get(key) == "on"

    try:
        gem_to_gold_ratio = float(form_data.get("gem_to_gold_ratio", "125"))
    except ValueError:
        gem_to_gold_ratio = 125.0

    return OptimizationSettings(
        use_gems=_flag("use_gems"),
        infinite_gold=_flag("infinite_gold"),
        keep_wild_card_buffer=not _flag("spend_wild_cards"),
        gem_to_gold_ratio=gem_to_gold_ratio,
    )


def _player_data_from_json(raw_json: str, catalog: CardCatalog) -> PlayerData:
    try:
        payload: Dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Player JSON could not be parsed. Please check the formatting.") from exc

    for card in payload.get("cards", []):
        if "rarity" not in card or not card["rarity"]:
            metadata = catalog.require(card["name"])
            card["rarity"] = metadata["rarity"]

    return PlayerData(**payload)


def _player_data_from_api(form_data: Dict[str, str]) -> PlayerData:
    tag = (form_data.get("player_tag") or "").strip().upper()
    if not tag:
        raise ValueError("Player tag is required when using RoyaleAPI.")

    try:
        gold = int(form_data.get("gold", "0").replace(",", ""))
        gems = int(form_data.get("gems", "0").replace(",", ""))
    except ValueError as exc:
        raise ValueError("Gold and Gems must be whole numbers.") from exc

    client = RoyaleAPIClient()
    snapshot = client.fetch_player_snapshot(tag)
    return player_data_from_snapshot(snapshot, gold=gold, gems=gems)


def _run_optimizer(player_data: PlayerData, settings: OptimizationSettings) -> OptimizationResult:
    optimizer = Level16Optimizer(player_data, settings=settings)
    return optimizer.generate_plan()


def _default_settings() -> OptimizationSettings:
    return OptimizationSettings(use_gems=False, infinite_gold=False, keep_wild_card_buffer=True, gem_to_gold_ratio=125.0)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")
catalog = CardCatalog()


@app.route("/", methods=["GET", "POST"])
def index():  # type: ignore[override]
    errors: list[str] = []
    result: OptimizationResult | None = None

    raw_json = request.form.get("player_json") or _sample_payload()
    player_tag = request.form.get("player_tag", "")
    gold_input = request.form.get("gold", "")
    gems_input = request.form.get("gems", "")
    source = request.form.get("source", "json")
    settings = _default_settings()

    if request.method == "POST":
        settings = _parse_settings(request.form)
        try:
            if source == "api":
                player_data = _player_data_from_api(request.form)
            else:
                player_data = _player_data_from_json(raw_json, catalog)

            result = _run_optimizer(player_data, settings)
        except (ValueError, ValidationError, RoyaleAPIError) as exc:
            errors.append(str(exc))

    return render_template(
        "index.html",
        raw_json=raw_json,
        sample_json=_sample_payload(),
        player_tag=player_tag,
        gold_input=gold_input,
        gems_input=gems_input,
        source=source,
        settings=settings,
        errors=errors,
        result=result,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "4000")), debug=True)
