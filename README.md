# Clash-Level-Calculator

Python implementation of the Level 16 Update Optimization Engine. The tool ingests your current Clash Royale inventory and returns the most efficient upgrade sequence to maximize King Tower XP under the current economy as of December 9th, 2025. Created and maintained by Nickolas Yang (ningkaiyang on Discord and Clash Royale).

## Web app (Flask)

Run a lightweight web UI locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m clash_level_calculator.web_app
# open http://localhost:4000
```

Features:

- Fetch a live snapshot via RoyaleAPI (`ROYALE_API_KEY` env var required).
- Toggle gem usage and infinite-gold mode; the UI keeps a 10% wild-card buffer by default.
- View a formatted upgrade table and projected King Level.

## Deploy to Render (free tier)

Render supports Python web services with `pip install` + `gunicorn`. This repo includes a `render.yaml` blueprint for one-click setup.

### Option A: Use render.yaml (recommended)

1. Push this branch to GitHub.
2. In the Render Dashboard, click **New → Blueprint** and select your repo.
3. Render will read `render.yaml` and propose a **Free** web service using `gunicorn clash_level_calculator.web_app:app`.
4. Create a Clash Royale Developer API key and whitelist the RoyaleAPI proxy IP: `45.79.218.79`.
5. Set environment variables as needed:
	- `ROYALE_API_KEY` (required for live player fetches) – your developer token tied to the whitelisted IP above.
	- `FLASK_SECRET_KEY` (optional) – session signing for Flask.
	- `ROYALE_API_BASE_URL` (optional) – override the default `https://proxy.royaleapi.dev/v1` base if you want to target the official API directly.
6. Deploy. Render will run `pip install -r requirements.txt` and bind the service to the port specified by the `PORT` environment variable.

### Option B: Manual Web Service setup

1. New → Web Service → connect this repo/branch.
2. Language: Python 3. Build command: `pip install -r requirements.txt`. Start command: `gunicorn --bind 0.0.0.0:$PORT clash_level_calculator.web_app:app`.
3. Whitelist `45.79.218.79` when creating your Clash Royale developer key; set `ROYALE_API_KEY` in Render.
4. (Optional) Set `ROYALE_API_BASE_URL` if you need to point at the official API instead of the RoyaleAPI proxy.
5. Instance type: Free. Add the env vars above if you want RoyaleAPI support. Consider setting a health check path under Advanced → Health Check Path (e.g., `/health`) to let Render verify the service is healthy.
6. Deploy; every push to this branch auto-redeploys.

## Quick start
Set a Clash Royale Developer API Key in your runtime environment (like zshrc) after whitelisting the RoyaleAPI proxy IP `45.79.218.79` when creating the key. The client uses `https://proxy.royaleapi.dev/v1` by default so no additional egress proxy is required. To hit the official API instead, export `ROYALE_API_BASE_URL=https://api.clashroyale.com/v1`.

Then, just run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m clash_level_calculator.cli
```

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
- `clash_level_calculator/clients/royale_api.py` – fully wired RoyaleAPI client ready for use with a Developer Key.

## Interactive RoyaleAPI workflow

To pull live data directly from the Clash Royale API:

1. Create a `.env` file that sets `ROYALE_API_KEY=<your developer token>` or manually insert key into the `./clash_level_calculator/clients/royale_api.py` file.
2. Run `python -m clash_level_calculator.interactive_cli`.
3. Enter your player tag (e.g., `#G2VV9802`), your current Gold, and your Gems when prompted.

The script fetches only the necessary fields (King Level XP and the entire card collection), then outputs three ranked upgrade paths:

- **All Resources** – spends Gold + Gems + cards resourcefully.
- **Gold + Cards Only** – keeps Gems untouched.
- **Card Bottleneck (Infinite Gold)** – ignores Gold limits but preserves true gold costs/ratios so the ranking stays meaningful while only card copies remain the bottleneck.

Wild Cards are intentionally ignored for this online workflow to keep the calculations faithful to the live collection data. For automated testing or offline demos you can supply a cached RoyaleAPI snapshot via `--offline-file examples/sample_player_snapshot.json` along with `--gold` and `--gems` arguments.

## Future API integration

The `RoyaleAPIClient` class exposes the base URL and key handling logic. Implement HTTP calls there, translate the response into the `PlayerData` schema, and the optimizer will immediately support live player data fetched via the official Clash Royale API.