import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from settings import get_settings_path, load_settings, save_settings

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

    def test_settings_path_uses_localappdata_without_portable_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_dir = root / "app"
            local_appdata = root / "localappdata"
            app_dir.mkdir()

            with patch("settings.get_app_dir", return_value=app_dir):
                with patch.dict(
                    "os.environ",
                    {"LOCALAPPDATA": str(local_appdata)},
                    clear=False,
                ):
                    path = get_settings_path()

            expected = local_appdata / "Focustime" / "settings.json"
            self.assertEqual(path, expected)

    def test_settings_path_uses_portable_data_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = Path(temp_dir)
            (app_dir / "portable.flag").touch()

            with patch("settings.get_app_dir", return_value=app_dir):
                path = get_settings_path()

            expected = app_dir / "data" / "settings.json"
            self.assertEqual(path, expected)

if __name__ == "__main__":
    unittest.main()