from __future__ import annotations

WHITE = "#FFFFFF"

PALETTES = {
    "dark": {
        "card": "#17181D", "border": "#2C2E38", "field": "#20222B",
        "text": "#E9EBF1", "body": "#B9BDC9", "muted": "#6C7080",
        "track": "#24262F", "focus": "#5B8DEF", "rest": "#3FBF7F",
        "warn": "#E06C6C", "hot": "#8FB2F6", "menu_text": "#FFFFFF",
    },
    "light": {
        "card": "#F7F8FA", "border": "#DCDFE6", "field": "#FFFFFF",
        "text": "#1C1E24", "body": "#4A4E58", "muted": "#8A8F9C",
        "track": "#E3E5EB", "focus": "#2F6BD4", "rest": "#1E9463",
        "warn": "#C6483F", "hot": "#1F4FA8", "menu_text": "#FFFFFF",
    },
}

P: dict[str, str] = dict(PALETTES["dark"])


def use_palette(name: str) -> None:
    P.clear()
    P.update(PALETTES.get(name, PALETTES["dark"]))

FONT_TIME = ("Segoe UI Semibold", 34)
FONT_LABEL = ("Segoe UI", 9)
FONT_BODY = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_HEAD = ("Segoe UI Semibold", 10)
FONT_EMOJI = ("Segoe UI Emoji", 15)
FONT_GLYPH = ("Segoe UI Symbol", 11)
