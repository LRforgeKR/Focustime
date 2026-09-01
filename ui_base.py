from __future__ import annotations

import tkinter as tk

from theme import FONT_BODY, P
from windows_utils import work_area


CHROMA = "#FF00FE"


def rounded(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    """Rettangolo con angoli arrotondati come singolo item del canvas."""
    pts = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]

    return canvas.create_polygon(
        pts,
        smooth=True,
        **kw,
    )


class Skin:
    """Associa gli elementi grafici ai colori della palette."""

    def __init__(self, canvas: tk.Canvas):
        self.c = canvas
        self._items: list[tuple[int, dict]] = []
        self._widgets: list[tuple[tk.Widget, dict]] = []

    def paint(self, item, **mapping):
        self._items.append((item, mapping))
        self.c.itemconfig(
            item,
            **{key: P[value] for key, value in mapping.items()},
        )
        return item

    def dress(self, widget, **mapping):
        self._widgets.append((widget, mapping))
        widget.config(
            **{key: P[value] for key, value in mapping.items()},
        )
        return widget

    def repaint(self):
        for item, mapping in self._items:
            try:
                self.c.itemconfig(
                    item,
                    **{key: P[value] for key, value in mapping.items()},
                )
            except tk.TclError:
                pass

        for widget, mapping in self._widgets:
            try:
                widget.config(
                    **{key: P[value] for key, value in mapping.items()},
                )
            except tk.TclError:
                pass


class Panel(tk.Toplevel):
    """Finestra secondaria trasparente e coerente con il tema."""

    def __init__(self, master, width, height):
        super().__init__(master)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=CHROMA)
        self.attributes("-transparentcolor", CHROMA)

        self.c = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=CHROMA,
            highlightthickness=0,
        )
        self.c.pack()

        self.skin = Skin(self.c)

        self._jobs: list[str] = []
        self._refreshers: list = []
        self._nodrag = False
        self._drag = None

    def later(self, ms, fn, *args):
        """Come after(), ma il lavoro in coda muore insieme al pannello."""
        job = self.after(ms, fn, *args)
        self._jobs.append(job)
        return job

    def destroy(self):
        for job in self._jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass

        self._jobs.clear()
        super().destroy()

    def card(self, width, height):
        item = rounded(
            self.c,
            1,
            1,
            width - 1,
            height - 1,
            12,
            width=1,
        )

        self.skin.paint(
            item,
            fill="card",
            outline="border",
        )

        self.c.tag_lower(item)
        return item

    def repaint(self):
        self.skin.repaint()

        for refresh in self._refreshers:
            refresh()

    def place_near(self, x, y, width, height, anchor=None, margin=8):
        """Posiziona il pannello restando all'interno del monitor."""
        ax, ay = anchor if anchor else (x, y)

        left, top, right, bottom = work_area(
            self,
            ax,
            ay,
        )

        x = max(
            left + margin,
            min(x, right - width - margin),
        )

        y = max(
            top + margin,
            min(y, bottom - height - margin),
        )

        self.geometry(
            f"{width}x{height}+{int(x)}+{int(y)}"
        )

    def below_or_above(self, wx, wy, ww, wh, width, height):
        """Posiziona il pannello sotto o sopra la finestra principale."""
        center = (
            wx + ww // 2,
            wy + wh // 2,
        )

        _left, top, _right, bottom = work_area(
            self,
            *center,
        )

        y = wy + wh + 8

        if (
            y + height > bottom - 8
            and wy - height - 8 >= top + 8
        ):
            y = wy - height - 8

        self.place_near(
            wx,
            y,
            width,
            height,
            anchor=center,
        )

    # -- trascinamento ------------------------------------------------ #

    def draggable(self):
        self.c.bind("<Button-1>", self._press)
        self.c.bind("<B1-Motion>", self._motion)
        self.c.bind("<ButtonRelease-1>", self._release)

    def _press(self, event):
        if self._nodrag or not self.winfo_exists():
            return

        self._drag = (
            event.x_root - self.winfo_x(),
            event.y_root - self.winfo_y(),
        )

    def _motion(self, event):
        if self._drag:
            dx, dy = self._drag

            self.geometry(
                f"+{event.x_root - dx}+{event.y_root - dy}"
            )

    def _release(self, _event):
        self._drag = None
        self._nodrag = False

    # -- comandi testuali --------------------------------------------- #

    def link(
        self,
        x,
        y,
        label,
        action,
        anchor="w",
        key="muted",
    ):
        c = self.c

        item = c.create_text(
            x,
            y,
            text=label,
            anchor=anchor,
            font=FONT_BODY,
        )

        self.skin.paint(item, fill=key)

        x1, y1, x2, y2 = c.bbox(item)

        pad = c.create_rectangle(
            x1 - 6,
            y1 - 5,
            x2 + 6,
            y2 + 5,
            outline="",
        )

        self.skin.paint(pad, fill="card")
        c.tag_lower(pad, item)

        def press(_event):
            self._nodrag = True
            self.later(1, action)

        for element in (pad, item):
            c.tag_bind(element, "<Button-1>", press)

            c.tag_bind(
                element,
                "<Enter>",
                lambda _event: (
                    c.itemconfig(item, fill=P["hot"]),
                    c.config(cursor="hand2"),
                ),
            )

            c.tag_bind(
                element,
                "<Leave>",
                lambda _event: (
                    c.itemconfig(item, fill=P[key]),
                    c.config(cursor=""),
                ),
            )

        return item