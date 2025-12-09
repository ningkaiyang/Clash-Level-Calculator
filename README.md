# Clash-Level-Calculator

Python implementation of the Level 16 Optimization Engine described in `.github/copilot-instructions.md`. The tool ingests your current Clash Royale inventory and returns the most efficient upgrade sequence to maximize King Tower XP under the current economy.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m clash_level_calculator.cli --player-data examples/sample_player.json
```

Useful flags:

- `--use-gems` – let the planner buy missing cards with gems (uses RoyaleAPI pricing table).
- `--infinite-gold` – ignore gold costs and maximize XP per card (materials bottleneck mode).
- `--no-wild-buffer` – spend all wild cards (default keeps a 10% emergency reserve).
- `--gem-gold-ratio` – adjust the gold-equivalent penalty applied per gem when ranking upgrades.

## Player data format

Supply a JSON file containing the fields below (see `examples/sample_player.json`). Card rarities are validated against the RoyaleAPI dataset bundled in `data/cards.json`. If a card entry is missing a `rarity`, it will be filled automatically from the catalog.

```json
{
	"profile": {"king_level": 52, "xp_into_level": 12000},
	"inventory": {
		"gold": 450000,
		"gems": 800,
		"wild_cards": {"Common": 12000, "Rare": 3000, "Epic": 500, "Legendary": 120, "Champion": 25}
	},
	"cards": [
		{"name": "Knight", "rarity": "Common", "level": 14, "count": 4000}
	]
}
```

## Architecture highlights

- `clash_level_calculator/constants.py` – single source of truth for gold costs, XP tables, gem values, and card material requirements.
- `clash_level_calculator/optimizer.py` – greedy engine that prioritizes Level 16/15 upgrades, recursively requeueing follow-up upgrades as resources allow.
- `clash_level_calculator/catalog.py` + `data/cards.json` – RoyaleAPI card metadata to validate names/rarities and keep the dataset in sync with the live game.
- `clash_level_calculator/clients/royale_api.py` – stubbed client showing where to plug in a Clash Royale Developer Key for automatic profile pulls in the next iteration.

## Future API integration

The `RoyaleAPIClient` class exposes the base URL and key handling logic. Implement HTTP calls there, translate the response into the `PlayerData` schema, and the optimizer will immediately support live player data fetched via the official Clash Royale API.
