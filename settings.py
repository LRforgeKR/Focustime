import json
import os
import sys

from pathlib import Path
from typing import Any


APP_NAME = "Focustime"
PORTABLE_FLAG = "portable.flag"


def get_app_dir() -> Path:
    """Restituisce la cartella reale dell'applicazione."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def is_portable_mode() -> bool:
    """True se accanto all'applicazione esiste portable.flag."""
    return (get_app_dir() / PORTABLE_FLAG).is_file()


def get_settings_path() -> Path:
    """Restituisce la posizione delle impostazioni dell'utente."""

    if is_portable_mode():
        return get_app_dir() / "data" / "settings.json"

    base = os.environ.get("LOCALAPPDATA")

    if base:
        return Path(base) / APP_NAME / "settings.json"

    # Fallback per sistemi dove LOCALAPPDATA non esiste.
    return Path.home() / ".focustime" / "settings.json"


def migrate_legacy_settings(legacy_path: Path, new_path: Path) -> None:
    """Copia le vecchie impostazioni nella nuova posizione, una sola volta."""
    if new_path.exists() or not legacy_path.exists():
        return

    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(
            legacy_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_settings(path: Path) -> dict[str, Any]:
    """Legge le impostazioni dal file JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def save_settings(path: Path, data: dict[str, Any]) -> bool:
    """Salva le impostazioni nel file JSON."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return True
    except (OSError, TypeError):
        return False