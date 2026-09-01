from __future__ import annotations

import tkinter as tk

from techniques import Technique, schema
from theme import (
    FONT_BODY,
    FONT_EMOJI,
    FONT_HEAD,
    FONT_LABEL,
    FONT_SMALL,
)
from ui_base import Panel
from windows_utils import work_area


class Toast(Panel):
    """Notifica discreta in basso a destra, coerente con l'app."""

    WIDTH, HEIGHT = 300, 78

    def __init__(
        self,
        master,
        emoji: str,
        title: str,
        body: str,
        accent: str,
    ):
        super().__init__(master, self.WIDTH, self.HEIGHT)
        self.attributes("-alpha", 0.0)

        # In basso a destra sul monitor dove sta l'app,
        # non necessariamente quello primario.
        cx = master.winfo_rootx() + master.winfo_width() // 2
        cy = master.winfo_rooty() + master.winfo_height() // 2

        _left, _top, right, bottom = work_area(
            self,
            cx,
            cy,
        )

        self.geometry(
            f"{self.WIDTH}x{self.HEIGHT}"
            f"+{right - self.WIDTH - 24}"
            f"+{bottom - self.HEIGHT - 24}"
        )

        c = self.c
        self.card(self.WIDTH, self.HEIGHT)

        self.skin.paint(
            c.create_line(
                11,
                20,
                11,
                self.HEIGHT - 20,
                width=3,
                capstyle="round",
            ),
            fill=accent,
        )

        self.skin.paint(
            c.create_text(
                38,
                self.HEIGHT / 2,
                text=emoji,
                font=FONT_EMOJI,
            ),
            fill="text",
        )

        self.skin.paint(
            c.create_text(
                62,
                30,
                text=title,
                anchor="w",
                font=("Segoe UI Semibold", 11),
            ),
            fill="text",
        )

        self.skin.paint(
            c.create_text(
                62,
                50,
                text=body,
                anchor="w",
                font=FONT_LABEL,
            ),
            fill="muted",
        )

        c.bind("<Button-1>", lambda _e: self.close())

        self._alpha = 0.0
        self._fade(0.08, 0.97)
        self.later(4200, self.close)

    def _fade(self, step: float, target: float, then=None):
        self._alpha = (
            min(target, self._alpha + step)
            if step > 0
            else max(target, self._alpha + step)
        )

        try:
            self.attributes("-alpha", self._alpha)
        except tk.TclError:
            return

        if abs(self._alpha - target) > 0.01:
            self.later(
                16,
                self._fade,
                step,
                target,
                then,
            )
        elif then:
            then()

    def close(self):
        if self.winfo_exists():
            self._fade(-0.1, 0.0, self.destroy)


class About(Panel):
    """Riquadro che spiega la tecnica, mostrato passando sul nome."""

    WIDTH = 300

    def __init__(
        self,
        master,
        t: Technique,
        wx: int,
        wy: int,
        ww: int,
        wh: int,
    ):
        super().__init__(master, self.WIDTH, 400)

        c, pad = self.c, 16

        self.skin.paint(
            c.create_text(
                pad + 30,
                pad + 2,
                text=t.name,
                anchor="nw",
                font=FONT_HEAD,
            ),
            fill="text",
        )

        self.skin.paint(
            c.create_text(
                pad + 10,
                pad + 10,
                text=t.emoji,
                anchor="center",
                font=("Segoe UI Emoji", 12),
            ),
            fill="text",
        )

        body = self.skin.paint(
            c.create_text(
                pad,
                pad + 26,
                text=t.about,
                anchor="nw",
                font=FONT_BODY,
                width=self.WIDTH - pad * 2,
                justify="left",
            ),
            fill="body",
        )

        bottom = c.bbox(body)[3]

        self.skin.paint(
            c.create_line(
                pad,
                bottom + 12,
                self.WIDTH - pad,
                bottom + 12,
            ),
            fill="track",
        )

        self.skin.paint(
            c.create_text(
                pad,
                bottom + 20,
                text=schema(t),
                anchor="nw",
                font=FONT_SMALL,
            ),
            fill="muted",
        )

        height = bottom + 44

        c.config(height=height)
        self.card(self.WIDTH, height)

        self.below_or_above(
            wx,
            wy,
            ww,
            wh,
            self.WIDTH,
            height,
        )