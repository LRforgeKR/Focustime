import tempfile
import unittest
from pathlib import Path

from settings import load_settings, save_settings


class SettingsTests(unittest.TestCase):

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            data = {
                "theme": "dark",
                "opacity": 85,
                "auto_next": True,
            }

            result = save_settings(path, data)

            self.assertTrue(result)
            self.assertEqual(load_settings(path), data)

    def test_missing_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.json"

            self.assertEqual(load_settings(path), {})

    def test_invalid_json_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("{invalid json", encoding="utf-8")

            self.assertEqual(load_settings(path), {})

    def test_non_dictionary_json_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text('["not", "a", "dictionary"]', encoding="utf-8")

            self.assertEqual(load_settings(path), {})


if __name__ == "__main__":
    unittest.main()