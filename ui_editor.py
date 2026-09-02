from __future__ import annotations

import tkinter as tk

from techniques import M, Technique, is_minutes_field
from theme import FONT_BODY, FONT_SMALL, P
from ui_base import Panel

class Editor(Panel):
    """Modifica le durate della tecnica corrente."""

    WIDTH = 292
    ROW = 32

    def __init__(
        self,
        master,
        t: Technique,
        base: Technique,
        on_save,
        on_close,
        max_cycle: int,
    ):
        self.t = t
        self.base = base
        self.on_save = on_save
        self.on_close = on_close
        self.max_cycle = max_cycle

        self.fields = self._spec()
        height = 48 + self.ROW * len(self.fields) + 50
        super().__init__(master, self.WIDTH, height)
        self.height = height
        self.card(self.WIDTH, height)

        c = self.c
        self.skin.paint(
            c.create_text(
                18, 26,
                text=f"{self.t.emoji}  {self.t.name}",
                anchor="w",
                font=("Segoe UI Emoji", 11),
            ),
            fill="text",
        )
        self.skin.paint(
            c.create_text(
                self.WIDTH - 18,
                26,
                text="DURATE",
                anchor="e",
                font=("Segoe UI Semibold", 8),
            ),
            fill="muted",
        )

        self.entries = {}
        y = 60

        for label, attr, lo, hi, unit in self.fields:
            self.skin.paint(
                c.create_text(
                    18,
                    y,
                    text=label,
                    anchor="w",
                    font=FONT_BODY,
                ),
                fill="body",
            )

            e = tk.Entry(
                self,
                width=4,
                justify="center",
                font=("Segoe UI", 10),
                relief="flat",
                highlightthickness=1,
            )

            self.skin.dress(
                e,
                bg="field",
                fg="text",
                insertbackground="text",
                highlightbackground="border",
                highlightcolor="focus",
            )

            e.insert(0, str(self._value(attr)))

            c.create_window(
                self.WIDTH - 52,
                y,
                window=e,
                anchor="e",
                height=24,
                width=48,
            )

            if unit:
                self.skin.paint(
                    c.create_text(
                        self.WIDTH - 18,
                        y,
                        text=unit,
                        anchor="e",
                        font=FONT_SMALL,
                    ),
                    fill="muted",
                )

            self.entries[attr] = e
            y += self.ROW

        fy = height - 26

        self.link(18, fy, "Ripristina", self.restore)
        self.link(self.WIDTH - 84, fy, "Annulla", self.close, anchor="e")
        self.link(
            self.WIDTH - 18,
            fy,
            "Salva",
            self.save,
            anchor="e",
            key="focus",
        )

        self.below_or_above(
            master.winfo_rootx(),
            master.winfo_rooty(),
            master.winfo_width(),
            master.winfo_height(),
            self.WIDTH,
            height,
        )

        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.close())
        self.draggable()

        next(iter(self.entries.values())).focus_set()
        self.later(50, self.focus_force)
    # -- struttura dei campi ------------------------------------------------ #

    def _spec(self):
        if self.base.ratio:
            return [
                ("Pausa = lavoro diviso", "ratio", 2, 20, ""),
                ("Pausa minima", "min_rest", 1, 120, "min"),
                ("Pausa massima", "max_rest", 1, 240, "min"),
            ]
        return [
            ("Focus", "focus", 1, 600, "min"),
            ("Pausa", "rest", 1, 600, "min"),
            ("Pausa lunga  (0 = nessuna)", "long_rest", 0, 600, "min"),
            ("Ogni quanti focus", "cycle", 2, self.max_cycle, ""),
        ]

    def _value(self, attr, t: Technique | None = None):
        v = getattr(t or self.t, attr)
        return v // M if is_minutes_field(attr) else v

    # -- comandi ------------------------------------------------------------ #

    def restore(self):
        for _l, attr, _lo, _hi, _u in self.fields:
            e = self.entries[attr]
            e.delete(0, "end")
            e.insert(0, str(self._value(attr, self.base)))

    def save(self):
        values, bad = {}, False
        for _l, attr, lo, hi, _u in self.fields:
            e = self.entries[attr]
            try:
                n = int(e.get().strip())
            except ValueError:
                n = None
            if n is None or not (lo <= n <= hi):
                e.config(highlightbackground=P["warn"], highlightcolor=P["warn"])
                bad = True
                continue
            e.config(highlightbackground=P["border"], highlightcolor=P["focus"])
            values[attr] = n
        if bad:
            return
        if "max_rest" in values:
            values["max_rest"] = max(values["max_rest"], values["min_rest"])
        self.on_save(values)
        self.close()

    def close(self):
        self.on_close()
        self.destroy()