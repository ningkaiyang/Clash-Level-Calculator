import unittest
from clash_level_calculator.api_adapter import player_data_from_snapshot
from clash_level_calculator.models import PlayerData, PlayerProfile, Inventory, Card

class TestApiAdapter(unittest.TestCase):

    def setUp(self):
        self.default_gold = 1000
        self.default_gems = 50

    def test_happy_path(self):
        snapshot = {
            "expLevel": 14,
            "expPoints": 300,
            "cards": [
                {
                    "name": "Knight",
                    "rarity": "Common",
                    "level": 14,
                    "count": 100
                },
                {
                    "name": "Fireball",
                    "rarity": "Rare",
                    "level": 11,
                    "count": 50
                }
            ]
        }

        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)

        self.assertEqual(player_data.profile.king_level, 14)
        self.assertEqual(player_data.profile.xp_into_level, 300)
        self.assertEqual(player_data.inventory.gold, self.default_gold)
        self.assertEqual(player_data.inventory.gems, self.default_gems)

        self.assertEqual(len(player_data.cards), 2)

        knight = next((c for c in player_data.cards if c.name == "Knight"), None)
        self.assertIsNotNone(knight)
        self.assertEqual(knight.rarity, "Common")
        self.assertEqual(knight.level, 14)
        self.assertEqual(knight.count, 100)

        fireball = next((c for c in player_data.cards if c.name == "Fireball"), None)
        self.assertIsNotNone(fireball)
        self.assertEqual(fireball.rarity, "Rare")
        self.assertEqual(fireball.level, 13) # Rare starts at 3 (level + offset) 11 + (3 - 1) = 13
        self.assertEqual(fireball.count, 50)

    def test_wild_cards_override(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 100,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        wild_cards = {"Common": 500, "Rare": 100, "Epic": 20, "Legendary": 5, "Champion": 1}

        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems, wild_cards)

        self.assertEqual(player_data.inventory.wild_cards, wild_cards)

    def test_missing_exp_points_defaults_to_zero(self):
        snapshot = {
            "expLevel": 10,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }

        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(player_data.profile.xp_into_level, 0)

        snapshot_none = {
            "expLevel": 10,
            "expPoints": None,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        player_data_none = player_data_from_snapshot(snapshot_none, self.default_gold, self.default_gems)
        self.assertEqual(player_data_none.profile.xp_into_level, 0)

    def test_invalid_exp_points_defaults_to_zero(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": "invalid",
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }

        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(player_data.profile.xp_into_level, 0)

    def test_king_level_clamping(self):
        snapshot_high = {
            "expLevel": 999,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        player_data_high = player_data_from_snapshot(snapshot_high, self.default_gold, self.default_gems)
        self.assertEqual(player_data_high.profile.king_level, 90) # Assuming 90 is max level

        snapshot_low = {
            "expLevel": -5,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        player_data_low = player_data_from_snapshot(snapshot_low, self.default_gold, self.default_gems)
        self.assertEqual(player_data_low.profile.king_level, 1)

    def test_xp_into_level_clamping(self):
        # Max xp_to_next for level 1 is 20
        snapshot_high_xp = {
            "expLevel": 1,
            "expPoints": 100,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 1, "count": 10}
            ]
        }
        player_data_high = player_data_from_snapshot(snapshot_high_xp, self.default_gold, self.default_gems)
        self.assertEqual(player_data_high.profile.xp_into_level, 20)

        snapshot_low_xp = {
            "expLevel": 1,
            "expPoints": -10,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 1, "count": 10}
            ]
        }
        player_data_low = player_data_from_snapshot(snapshot_low_xp, self.default_gold, self.default_gems)
        self.assertEqual(player_data_low.profile.xp_into_level, 0)

    def test_missing_card_fields_skip_card(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": 10},
                {"rarity": "Common", "level": 10, "count": 10}, # missing name
                {"name": "Goblins", "level": 10, "count": 10}, # missing rarity
                {"name": "Archers", "rarity": "Common", "count": 10}, # missing level
            ]
        }
        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(len(player_data.cards), 1)
        self.assertEqual(player_data.cards[0].name, "Knight")

    def test_invalid_rarity_skips_card(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Mythic", "level": 10, "count": 10}, # invalid
                {"name": "Archers", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        with self.assertRaises(ValueError):
            player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)

    def test_invalid_card_level_skips_card(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": "invalid", "count": 10},
                {"name": "Archers", "rarity": "Common", "level": 10, "count": 10}
            ]
        }
        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(len(player_data.cards), 1)
        self.assertEqual(player_data.cards[0].name, "Archers")

    def test_card_level_clamping(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 999, "count": 10},
                {"name": "Archers", "rarity": "Common", "level": -5, "count": 10}
            ]
        }
        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(len(player_data.cards), 2)
        self.assertEqual(player_data.cards[0].level, 16) # Cap is 16
        self.assertEqual(player_data.cards[1].level, 1) # Min is 1

    def test_invalid_card_count_defaults_to_zero(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"name": "Knight", "rarity": "Common", "level": 10, "count": "invalid"},
                {"name": "Archers", "rarity": "Common", "level": 10, "count": -50}
            ]
        }
        player_data = player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)
        self.assertEqual(len(player_data.cards), 2)
        self.assertEqual(player_data.cards[0].count, 0)
        self.assertEqual(player_data.cards[1].count, 0)

    def test_no_valid_cards_raises_error(self):
        snapshot = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": []
        }
        with self.assertRaisesRegex(ValueError, "RoyaleAPI snapshot did not include any cards to optimize"):
            player_data_from_snapshot(snapshot, self.default_gold, self.default_gems)

        snapshot_invalid_only = {
            "expLevel": 10,
            "expPoints": 0,
            "cards": [
                {"rarity": "Common", "level": 10, "count": 10} # skipped
            ]
        }
        with self.assertRaisesRegex(ValueError, "RoyaleAPI snapshot did not include any cards to optimize"):
            player_data_from_snapshot(snapshot_invalid_only, self.default_gold, self.default_gems)

if __name__ == '__main__':
    unittest.main()
