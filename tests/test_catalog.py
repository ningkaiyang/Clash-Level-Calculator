import unittest
from unittest.mock import patch

from clash_level_calculator.catalog import CardCatalog

class TestCardCatalog(unittest.TestCase):

    @patch("clash_level_calculator.catalog.requests.get")
    def test_find_by_name(self, mock_get):
        mock_get.return_value.json.return_value = [
            {"name": "Knight", "key": "knight", "rarity": "Common"},
            {"name": "Baby Dragon", "key": "baby-dragon", "rarity": "Epic"}
        ]

        catalog = CardCatalog()

        self.assertEqual(catalog.find("Knight"), {"name": "Knight", "key": "knight", "rarity": "Common"})
        self.assertEqual(catalog.find("knight"), {"name": "Knight", "key": "knight", "rarity": "Common"})
        self.assertEqual(catalog.find("KNIGHT"), {"name": "Knight", "key": "knight", "rarity": "Common"})
        self.assertEqual(catalog.find(" Baby Dragon "), {"name": "Baby Dragon", "key": "baby-dragon", "rarity": "Epic"})

    @patch("clash_level_calculator.catalog.requests.get")
    def test_find_by_key(self, mock_get):
        mock_get.return_value.json.return_value = [
            {"name": "Knight", "key": "knight", "rarity": "Common"},
            {"name": "Baby Dragon", "key": "baby-dragon", "rarity": "Epic"}
        ]

        catalog = CardCatalog()

        self.assertEqual(catalog.find("baby-dragon"), {"name": "Baby Dragon", "key": "baby-dragon", "rarity": "Epic"})
        self.assertEqual(catalog.find("BABY-DRAGON"), {"name": "Baby Dragon", "key": "baby-dragon", "rarity": "Epic"})

    @patch("clash_level_calculator.catalog.requests.get")
    def test_find_not_found(self, mock_get):
        mock_get.return_value.json.return_value = [
            {"name": "Knight", "key": "knight", "rarity": "Common"}
        ]

        catalog = CardCatalog()

        self.assertIsNone(catalog.find("Missing Card"))
        self.assertIsNone(catalog.find(""))
