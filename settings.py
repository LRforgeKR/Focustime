import json
from pathlib import Path
from typing import Any


def load_settings(path: Path) -> dict[str, Any]:
    """Legge le impostazioni dal file JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(path: Path, data: dict[str, Any]) -> bool:
    """Salva le impostazioni nel file JSON."""
    try:
        path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False