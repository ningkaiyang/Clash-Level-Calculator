import sys
from unittest.mock import MagicMock

# Mock pydantic to avoid ModuleNotFoundError in environments where it's not installed.
# This is necessary because clash_level_calculator/__init__.py imports modules that depend on pydantic.
if "pydantic" not in sys.modules:
    mock_pydantic = MagicMock()
    sys.modules["pydantic"] = mock_pydantic
    mock_pydantic.BaseModel = MagicMock
    mock_pydantic.Field = MagicMock

import unittest
from clash_level_calculator.game_data import GameData

class TestGameData(unittest.TestCase):
    def setUp(self):
        self.game_data = GameData()

    def test_total_xp_for_level_min(self):
        # Level 1 is the minimum level, should have 0 cumulative XP
        self.assertEqual(self.game_data.total_xp_for_level(1), 0)

    def test_total_xp_for_level_max(self):
        # Test the maximum level defined in the data
        max_row = self.game_data.king_levels[-1]
        max_level = max_row["level"]
        expected_xp = max_row["cumulative"]
        self.assertEqual(self.game_data.total_xp_for_level(max_level), expected_xp)

    def test_total_xp_for_level_mid(self):
        # Test a mid-range level (e.g., 50)
        # Find the row for level 50
        level_50_row = next(row for row in self.game_data.king_levels if row["level"] == 50)
        expected_xp = level_50_row["cumulative"]
        self.assertEqual(self.game_data.total_xp_for_level(50), expected_xp)

    def test_total_xp_for_level_below_min(self):
        # Levels below 1 should be clamped to 1 (XP 0)
        self.assertEqual(self.game_data.total_xp_for_level(0), 0)
        self.assertEqual(self.game_data.total_xp_for_level(-10), 0)

    def test_total_xp_for_level_above_max(self):
        # Levels above max should be clamped to the maximum level's XP
        max_row = self.game_data.king_levels[-1]
        max_level = max_row["level"]
        expected_xp = max_row["cumulative"]
        self.assertEqual(self.game_data.total_xp_for_level(max_level + 1), expected_xp)
        self.assertEqual(self.game_data.total_xp_for_level(max_level + 100), expected_xp)

if __name__ == "__main__":
    unittest.main()
