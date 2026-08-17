"""Focustime — timer minimale per la concentrazione.

Finestra senza bordi, sempre in primo piano, trascinabile.
Cinque tecniche di concentrazione, ognuna con la sua emoji e le sue durate.
Tema chiaro o scuro, pannello Preferenze e editor delle durate dal tasto destro.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass, replace
from pathlib import Path

try:
    import winsound
except ImportError:  # non-Windows: l'app resta usabile, senza suoni
    winsound = None

try:
    import ctypes
except ImportError:
    ctypes = None


__version__ = "1.0.0"
REPO_URL = "https://github.com/LRforgeKR/Focustime"

M = 60


def app_dir() -> Path:
    """Cartella dell'app: quella dell'exe se compilata, del sorgente altrimenti.

    In un eseguibile PyInstaller `__file__` punta alla cartella temporanea di
    estrazione, che sparisce alla chiusura: non va mai usata per salvare nulla
    né come cartella di lavoro di un collegamento.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Monitor
#
# Tkinter conosce solo lo schermo principale: winfo_screenwidth() ignora gli
# altri monitor. Senza questo, ogni pannello verrebbe riportato a forza sullo
# schermo primario appena sposti l'app su un secondo monitor.
# --------------------------------------------------------------------------- #

if ctypes is not None:

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT),
                    ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]

NEAREST, NONE = 2, 0


def _monitor(x, y, flag):
    if ctypes is None or not hasattr(ctypes, "windll"):
        return None
    try:
        return ctypes.windll.user32.MonitorFromPoint(_POINT(int(x), int(y)), flag)
    except Exception:
        return None


def work_area(widget, x, y) -> tuple[int, int, int, int]:
    """Area utile (barra applicazioni esclusa) del monitor che contiene x, y."""
    h = _monitor(x, y, NEAREST)
    if h:
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        try:
            if ctypes.windll.user32.GetMonitorInfoW(h, ctypes.byref(mi)):
                r = mi.rcWork
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()


def on_a_monitor(x, y) -> bool | None:
    """Il punto cade dentro uno degli schermi collegati?"""
    if ctypes is None or not hasattr(ctypes, "windll"):
        return None            # non lo sappiamo: decide chi chiama
    return bool(_monitor(x, y, NONE))


# --------------------------------------------------------------------------- #
# Avvio automatico con Windows
# --------------------------------------------------------------------------- #

LINK_NAME = "Focustime.lnk"
NO_WINDOW = 0x08000000


def startup_link() -> Path:
    base = os.environ.get("APPDATA", "")
    return (Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "Startup" / LINK_NAME)


def starts_with_windows() -> bool:
    try:
        return startup_link().exists()
    except Exception:
        return False


def set_starts_with_windows(on: bool) -> bool:
    """Crea o toglie il collegamento nella cartella Esecuzione automatica."""
    link = startup_link()
    if not on:
        try:
            link.unlink(missing_ok=True)
        except OSError:
            pass
        return starts_with_windows()

    if getattr(sys, "frozen", False):
        target, args = Path(sys.executable), ""
    else:
        exe = Path(sys.executable)
        quiet = exe.with_name("pythonw.exe")       # niente finestra nera
        target = quiet if quiet.exists() else exe
        args = f'"{Path(__file__).resolve()}"'
    workdir = app_dir()

    def q(value):                                  # apici nelle stringhe PS
        return str(value).replace("'", "''")

    script = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(link)}');"
        f"$s.TargetPath='{q(target)}';"
        f"$s.Arguments='{q(args)}';"
        f"$s.WorkingDirectory='{q(workdir)}';"
        f"$s.Description='Focustime';$s.Save()"
    )
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                        "-Command", script],
                       creationflags=NO_WINDOW, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return starts_with_windows()


# --------------------------------------------------------------------------- #
# Tecniche
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Technique:
    key: str
    emoji: str
    name: str
    focus: int              # durata focus in secondi (0 = cronometro in salita)
    rest: int               # pausa breve
    long_rest: int = 0      # pausa lunga (0 = nessuna)
    cycle: int = 4          # focus da completare prima della pausa lunga
    ratio: int = 0          # Flowtime: pausa = focus lavorato / ratio
    min_rest: int = 3 * M   # Flowtime: pausa minima
    max_rest: int = 30 * M  # Flowtime: pausa massima
    about: str = ""         # spiegazione mostrata passando sul nome


TECHNIQUES: list[Technique] = [
    Technique(
        "pomodoro", "\U0001F345", "Pomodoro", 25 * M, 5 * M, 15 * M, 4,
        about="Venticinque minuti su un compito solo, poi cinque di stacco; "
              "ogni quattro giri una pausa lunga. Nasce negli anni '80 da un "
              "timer da cucina a forma di pomodoro. Serve a rendere il tempo "
              "una cosa che vedi scorrere, e a spezzare i compiti grossi in "
              "pezzi che non fanno paura.",
    ),
    Technique(
        "5217", "⚡", "52 / 17", 52 * M, 17 * M,
        about="Cinquantadue minuti di lavoro pieno e diciassette di stacco "
              "vero. È il ritmo emerso dai dati di DeskTime osservando chi "
              "rendeva di più: poche pause, ma lunghe abbastanza da "
              "ricaricare davvero. Buona per una normale giornata al computer.",
    ),
    Technique(
        "ultradian", "\U0001F30A", "Ultradian", 90 * M, 20 * M,
        about="Novanta minuti seguono il ritmo ultradiano del cervello, lo "
              "stesso che scandisce il sonno: circa un'ora e mezza di "
              "attenzione, poi un calo fisiologico. È la tecnica del lavoro "
              "profondo — partire costa di più, ma arrivi molto più a fondo.",
    ),
    Technique(
        "flowtime", "\U0001F300", "Flowtime", 0, 0, ratio=5,
        about="Nessun timer che ti interrompe: il cronometro sale e sei tu a "
              "fermarlo quando senti che stai calando. La pausa la calcola "
              "sul lavoro fatto, un quinto del tempo. Pensata per chi viene "
              "buttato fuori dalla concentrazione da una campanella.",
    ),
    Technique(
        "animedoro", "\U0001F3AC", "Animedoro", 40 * M, 20 * M,
        about="Quaranta minuti di lavoro e venti di pausa lunga e piacevole, "
              "il tempo di un episodio. La ricompensa è abbastanza grande da "
              "farti venire voglia di arrivarci: funziona bene la sera e "
              "quando il compito è noioso.",
    ),
]


# --------------------------------------------------------------------------- #
# Temi
# --------------------------------------------------------------------------- #

W, H = 250, 128
CHROMA = "#FF00FE"          # colore-chiave reso trasparente da Windows
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


def use_palette(name: str):
    P.clear()
    P.update(PALETTES.get(name, PALETTES["dark"]))


def system_prefers_dark() -> bool | None:
    """Windows è impostato su scuro? None se non riusciamo a saperlo."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        with key:
            light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return not bool(light)
    except Exception:
        return None


FONT_TIME = ("Segoe UI Semibold", 34)
FONT_LABEL = ("Segoe UI", 9)
FONT_BODY = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_HEAD = ("Segoe UI Semibold", 10)
FONT_EMOJI = ("Segoe UI Emoji", 15)
FONT_GLYPH = ("Segoe UI Symbol", 11)

MAX_DOTS = 8
MIN_ALPHA = 55


def rounded(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    """Rettangolo con angoli arrotondati come singolo item del canvas."""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def mmss(seconds: float) -> str:
    seconds = max(0, int(seconds + 0.5))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def beep(pattern: list[tuple[int, int]]) -> None:
    """Suona una sequenza (frequenza, durata) senza bloccare la UI."""
    if winsound is None:
        return

    def run():
        try:
            for freq, dur in pattern:
                winsound.Beep(freq, dur)
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


def schema(t: Technique) -> str:
    """Riga che riassume le durate della tecnica."""
    if t.ratio:
        return (f"pausa = lavoro ÷ {t.ratio}, "
                f"da {t.min_rest // M} a {t.max_rest // M} min")
    parts = [f"{t.focus // M} min focus", f"{t.rest // M} pausa"]
    if t.long_rest:
        parts.append(f"{t.long_rest // M} lunga ogni {t.cycle}")
    return " · ".join(parts)


class Skin:
    """Ricorda quale colore della palette ha ogni elemento.

    Serve a ridipingere tutto al cambio di tema senza ricostruire le finestre.
    """

    def __init__(self, canvas: tk.Canvas):
        self.c = canvas
        self._items: list[tuple[int, dict]] = []
        self._widgets: list[tuple[tk.Widget, dict]] = []

    def paint(self, item, **mapping):
        self._items.append((item, mapping))
        self.c.itemconfig(item, **{k: P[v] for k, v in mapping.items()})
        return item

    def dress(self, widget, **mapping):
        self._widgets.append((widget, mapping))
        widget.config(**{k: P[v] for k, v in mapping.items()})
        return widget

    def repaint(self):
        for item, mapping in self._items:
            try:
                self.c.itemconfig(item, **{k: P[v] for k, v in mapping.items()})
            except tk.TclError:
                pass
        for widget, mapping in self._widgets:
            try:
                widget.config(**{k: P[v] for k, v in mapping.items()})
            except tk.TclError:
                pass


class Panel(tk.Toplevel):
    """Finestrella scura o chiara con angoli arrotondati."""

    def __init__(self, master, width, height):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=CHROMA)
        self.attributes("-transparentcolor", CHROMA)
        self.c = tk.Canvas(self, width=width, height=height, bg=CHROMA,
                           highlightthickness=0)
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
        item = rounded(self.c, 1, 1, width - 1, height - 1, 12, width=1)
        self.skin.paint(item, fill="card", outline="border")
        self.c.tag_lower(item)
        return item

    def repaint(self):
        self.skin.repaint()
        for refresh in self._refreshers:
            refresh()

    def place_near(self, x, y, width, height, anchor=None, margin=8):
        """Posiziona il pannello restando dentro il monitor giusto.

        `anchor` è il punto che decide di quale monitor si tratta: di norma
        la finestra principale, non il pannello, che potrebbe sporgere.
        """
        ax, ay = anchor if anchor else (x, y)
        left, top, right, bottom = work_area(self, ax, ay)
        x = max(left + margin, min(x, right - width - margin))
        y = max(top + margin, min(y, bottom - height - margin))
        self.geometry(f"{width}x{height}+{int(x)}+{int(y)}")

    def below_or_above(self, wx, wy, ww, wh, width, height):
        """Sotto la finestra se c'è posto su quel monitor, altrimenti sopra."""
        center = (wx + ww // 2, wy + wh // 2)
        _l, top, _r, bottom = work_area(self, *center)
        y = wy + wh + 8
        if y + height > bottom - 8 and wy - height - 8 >= top + 8:
            y = wy - height - 8
        self.place_near(wx, y, width, height, anchor=center)

    # -- trascinamento ------------------------------------------------------ #

    def draggable(self):
        self.c.bind("<Button-1>", self._press)
        self.c.bind("<B1-Motion>", self._motion)
        self.c.bind("<ButtonRelease-1>", self._release)

    def _press(self, e):
        if self._nodrag or not self.winfo_exists():
            return
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _motion(self, e):
        if self._drag:
            dx, dy = self._drag
            self.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _release(self, _e):
        self._drag = None
        self._nodrag = False

    # -- comandi testuali --------------------------------------------------- #

    def link(self, x, y, label, action, anchor="w", key="muted"):
        c = self.c
        item = c.create_text(x, y, text=label, anchor=anchor, font=FONT_BODY)
        self.skin.paint(item, fill=key)
        x1, y1, x2, y2 = c.bbox(item)
        pad = c.create_rectangle(x1 - 6, y1 - 5, x2 + 6, y2 + 5, outline="")
        self.skin.paint(pad, fill="card")
        c.tag_lower(pad, item)

        def press(_e):
            self._nodrag = True
            self.later(1, action)

        for it in (pad, item):
            c.tag_bind(it, "<Button-1>", press)
            c.tag_bind(it, "<Enter>", lambda _e: (c.itemconfig(item, fill=P["hot"]),
                                                  c.config(cursor="hand2")))
            c.tag_bind(it, "<Leave>", lambda _e: (c.itemconfig(item, fill=P[key]),
                                                  c.config(cursor="")))
        return item


# --------------------------------------------------------------------------- #
# Notifica
# --------------------------------------------------------------------------- #

class Toast(Panel):
    """Notifica discreta in basso a destra, coerente con l'app."""

    WIDTH, HEIGHT = 300, 78

    def __init__(self, master, emoji: str, title: str, body: str, accent: str):
        super().__init__(master, self.WIDTH, self.HEIGHT)
        self.attributes("-alpha", 0.0)

        # in basso a destra sul monitor dove sta l'app, non sempre il primario
        cx = master.winfo_rootx() + master.winfo_width() // 2
        cy = master.winfo_rooty() + master.winfo_height() // 2
        _l, _t, right, bottom = work_area(self, cx, cy)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}"
                      f"+{right - self.WIDTH - 24}+{bottom - self.HEIGHT - 24}")

        c = self.c
        self.card(self.WIDTH, self.HEIGHT)
        self.skin.paint(
            c.create_line(11, 20, 11, self.HEIGHT - 20, width=3,
                          capstyle="round"), fill=accent)
        self.skin.paint(
            c.create_text(38, self.HEIGHT / 2, text=emoji, font=FONT_EMOJI),
            fill="text")
        self.skin.paint(
            c.create_text(62, 30, text=title, anchor="w",
                          font=("Segoe UI Semibold", 11)), fill="text")
        self.skin.paint(
            c.create_text(62, 50, text=body, anchor="w", font=FONT_LABEL),
            fill="muted")
        c.bind("<Button-1>", lambda _e: self.close())

        self._alpha = 0.0
        self._fade(0.08, 0.97)
        self.later(4200, self.close)

    def _fade(self, step: float, target: float, then=None):
        self._alpha = min(target, self._alpha + step) if step > 0 else \
            max(target, self._alpha + step)
        try:
            self.attributes("-alpha", self._alpha)
        except tk.TclError:
            return
        if abs(self._alpha - target) > 0.01:
            self.later(16, self._fade, step, target, then)
        elif then:
            then()

    def close(self):
        if self.winfo_exists():
            self._fade(-0.1, 0.0, self.destroy)


# --------------------------------------------------------------------------- #
# Spiegazione della tecnica
# --------------------------------------------------------------------------- #

class About(Panel):
    """Riquadro che spiega la tecnica, mostrato passando sul nome."""

    WIDTH = 300

    def __init__(self, master, t: Technique, wx: int, wy: int, ww: int, wh: int):
        super().__init__(master, self.WIDTH, 400)
        c, pad = self.c, 16
        self.skin.paint(
            c.create_text(pad + 30, pad + 2, text=t.name, anchor="nw",
                          font=FONT_HEAD), fill="text")
        self.skin.paint(
            c.create_text(pad + 10, pad + 10, text=t.emoji, anchor="center",
                          font=("Segoe UI Emoji", 12)), fill="text")
        body = self.skin.paint(
            c.create_text(pad, pad + 26, text=t.about, anchor="nw",
                          font=FONT_BODY, width=self.WIDTH - pad * 2,
                          justify="left"), fill="body")
        bottom = c.bbox(body)[3]
        self.skin.paint(c.create_line(pad, bottom + 12, self.WIDTH - pad,
                                      bottom + 12), fill="track")
        self.skin.paint(
            c.create_text(pad, bottom + 20, text=schema(t), anchor="nw",
                          font=FONT_SMALL), fill="muted")
        height = bottom + 44

        c.config(height=height)
        self.card(self.WIDTH, height)
        self.below_or_above(wx, wy, ww, wh, self.WIDTH, height)


# --------------------------------------------------------------------------- #
# Editor delle durate
# --------------------------------------------------------------------------- #

class Editor(Panel):
    """Modifica le durate della tecnica corrente."""

    WIDTH = 292
    ROW = 32

    def __init__(self, app: "Focustime"):
        self.app = app
        self.t = app.tech
        self.base = TECHNIQUES[app.index]
        self.fields = self._spec()
        height = 48 + self.ROW * len(self.fields) + 50
        super().__init__(app.root, self.WIDTH, height)
        self.height = height
        self.card(self.WIDTH, height)

        c = self.c
        self.skin.paint(
            c.create_text(18, 26, text=f"{self.t.emoji}  {self.t.name}",
                          anchor="w", font=("Segoe UI Emoji", 11)), fill="text")
        self.skin.paint(
            c.create_text(self.WIDTH - 18, 26, text="DURATE", anchor="e",
                          font=("Segoe UI Semibold", 8)), fill="muted")

        self.entries = {}
        y = 60
        for label, attr, lo, hi, unit in self.fields:
            self.skin.paint(
                c.create_text(18, y, text=label, anchor="w", font=FONT_BODY),
                fill="body")
            e = tk.Entry(self, width=4, justify="center", font=("Segoe UI", 10),
                         relief="flat", highlightthickness=1)
            self.skin.dress(e, bg="field", fg="text", insertbackground="text",
                            highlightbackground="border", highlightcolor="focus")
            e.insert(0, str(self._value(attr)))
            c.create_window(self.WIDTH - 52, y, window=e, anchor="e",
                            height=24, width=48)
            if unit:
                self.skin.paint(
                    c.create_text(self.WIDTH - 18, y, text=unit, anchor="e",
                                  font=FONT_SMALL), fill="muted")
            self.entries[attr] = e
            y += self.ROW

        fy = height - 26
        self.link(18, fy, "Ripristina", self.restore)
        self.link(self.WIDTH - 84, fy, "Annulla", self.close, anchor="e")
        self.link(self.WIDTH - 18, fy, "Salva", self.save, anchor="e",
                  key="focus")

        self.below_or_above(app.root.winfo_rootx(), app.root.winfo_rooty(),
                            W, H, self.WIDTH, height)
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
            ("Ogni quanti focus", "cycle", 2, MAX_DOTS, ""),
        ]

    @staticmethod
    def _is_minutes(attr):
        return attr in ("focus", "rest", "long_rest", "min_rest", "max_rest")

    def _value(self, attr, t: Technique | None = None):
        v = getattr(t or self.t, attr)
        return v // M if self._is_minutes(attr) else v

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
        self.app.apply_custom(values)
        self.close()

    def close(self):
        self.app.editor = None
        self.destroy()


# --------------------------------------------------------------------------- #
# Preferenze
# --------------------------------------------------------------------------- #

class Prefs(Panel):
    """Pannello delle impostazioni."""

    WIDTH = 306
    ROW = 30

    def __init__(self, app: "Focustime"):
        self.app = app
        rows = self._rows()
        height = 52 + sum(r[0] for r in rows) + 46
        super().__init__(app.root, self.WIDTH, height)
        self.card(self.WIDTH, height)

        c = self.c
        self.skin.paint(
            c.create_text(18, 28, text="Preferenze", anchor="w", font=FONT_HEAD),
            fill="text")
        self.skin.paint(
            c.create_text(self.WIDTH - 18, 28, text="FOCUSTIME", anchor="e",
                          font=("Segoe UI Semibold", 8)), fill="muted")

        y = 52
        for span, build in rows:
            build(y + span // 2)
            y += span

        fy = height - 24
        self.link(18, fy, "Durate…", self.open_durations)
        self.link(self.WIDTH - 76, fy, "Ripristina", self.restore, anchor="e")
        self.link(self.WIDTH - 18, fy, "Chiudi", self.close, anchor="e",
                  key="focus")

        self.below_or_above(app.root.winfo_rootx(), app.root.winfo_rooty(),
                            W, H, self.WIDTH, height)
        self.bind("<Escape>", lambda _e: self.close())
        self.draggable()
        self.later(50, self.focus_force)

    # -- righe -------------------------------------------------------------- #

    def _rows(self):
        a = self.app
        return [
            (36, lambda y: self._segment(
                y, "Tema", [("dark", "Scuro"), ("light", "Chiaro"),
                            ("auto", "Auto")],
                lambda: a.theme_mode, a.set_theme_mode)),
            (34, lambda y: self._slider(
                y, "Opacità", MIN_ALPHA, 100,
                lambda: a.opacity, a.set_opacity)),
            (12, self._rule),
            (self.ROW, lambda y: self._toggle(
                y, "Sempre in primo piano", a.on_top, a.apply_on_top)),
            (self.ROW, lambda y: self._toggle(
                y, "Avvia la fase successiva da solo", a.auto_next)),
            (self.ROW, lambda y: self._toggle(
                y, "Spiegazione al passaggio del mouse", a.about_on)),
            (12, self._rule),
            (self.ROW, lambda y: self._toggle(
                y, "Suoni a fine fase", a.sound_on)),
            (self.ROW, lambda y: self._toggle(y, "Notifiche", a.notify_on)),
            (12, self._rule),
            (self.ROW, lambda y: self._toggle(
                y, "Avvia Focustime con Windows", a.startup)),
            (12, self._rule),
            (26, self._info),
        ]

    def _info(self, y):
        """Piccola sezione con la versione e il collegamento al progetto."""
        self.skin.paint(
            self.c.create_text(18, y, text=f"Focustime {__version__}",
                               anchor="w", font=FONT_SMALL), fill="muted")
        self.link(self.WIDTH - 18, y, "GitHub ↗", self.open_repo, anchor="e")

    def _rule(self, y):
        self.skin.paint(self.c.create_line(18, y, self.WIDTH - 18, y),
                        fill="track")

    def _row_area(self, y):
        item = self.c.create_rectangle(8, y - 14, self.WIDTH - 8, y + 14,
                                       outline="")
        self.skin.paint(item, fill="card")
        return item

    def _label(self, y, text):
        item = self.c.create_text(18, y, text=text, anchor="w", font=FONT_BODY)
        self.skin.paint(item, fill="body")
        return item

    def _clickable(self, items, action):
        for it in items:
            self.c.tag_bind(it, "<Button-1>", action)
            self.c.tag_bind(it, "<Enter>",
                            lambda _e: self.c.config(cursor="hand2"))
            self.c.tag_bind(it, "<Leave>", lambda _e: self.c.config(cursor=""))

    # -- controlli ---------------------------------------------------------- #

    def _toggle(self, y, label, var: tk.BooleanVar, on_change=None):
        c = self.c
        area = self._row_area(y)
        lab = self._label(y, label)
        x2 = self.WIDTH - 18
        x1 = x2 - 34
        track = rounded(c, x1, y - 9, x2, y + 9, 9, outline="")
        knob = c.create_oval(0, 0, 0, 0, outline="")

        def draw():
            on = bool(var.get())
            c.itemconfig(track, fill=P["focus"] if on else P["track"])
            kx = x2 - 9 if on else x1 + 9
            c.coords(knob, kx - 6, y - 6, kx + 6, y + 6)
            c.itemconfig(knob, fill=WHITE if on else P["muted"])

        def click(_e):
            self._nodrag = True
            var.set(not bool(var.get()))
            draw()
            if on_change:
                on_change()

        self._clickable((area, lab, track, knob), click)
        self._refreshers.append(draw)
        draw()

    def _segment(self, y, label, options, get, set_):
        c = self.c
        self._label(y, label)
        cell_w, x2 = 56, self.WIDTH - 18
        x1 = x2 - cell_w * len(options)
        frame = rounded(c, x1, y - 12, x2, y + 12, 12, width=1)
        self.skin.paint(frame, fill="field", outline="border")

        cells = []
        for i, (value, text) in enumerate(options):
            cx = x1 + cell_w * i
            box = rounded(c, cx + 2, y - 10, cx + cell_w - 2, y + 10, 10,
                          outline="")
            txt = c.create_text(cx + cell_w / 2, y, text=text, font=FONT_SMALL)
            cells.append((value, box, txt))
            self._clickable((box, txt), lambda _e, v=value: pick(v))

        def draw():
            current = get()
            for value, box, txt in cells:
                chosen = value == current
                c.itemconfig(box, fill=P["focus"] if chosen else P["field"])
                c.itemconfig(txt, fill=WHITE if chosen else P["muted"])

        def pick(value):
            self._nodrag = True
            set_(value)
            draw()

        self._refreshers.append(draw)
        draw()

    def _slider(self, y, label, lo, hi, get, set_):
        c = self.c
        lab = self._label(y, f"{label}  {get()}%")
        x2, width = self.WIDTH - 18, 120
        x1 = x2 - width
        rail = c.create_line(x1, y, x2, y, width=3, capstyle="round")
        self.skin.paint(rail, fill="track")
        fill = c.create_line(x1, y, x1, y, width=3, capstyle="round")
        knob = c.create_oval(0, 0, 0, 0, outline="")

        def draw():
            value = min(hi, max(lo, get()))
            frac = (value - lo) / (hi - lo)
            kx = x1 + frac * width
            c.coords(fill, x1, y, max(x1 + 0.1, kx), y)
            c.itemconfig(fill, fill=P["focus"])
            c.coords(knob, kx - 7, y - 7, kx + 7, y + 7)
            c.itemconfig(knob, fill=P["focus"])
            c.itemconfig(lab, text=f"{label}  {value}%")

        def move(e):
            self._nodrag = True
            frac = min(1.0, max(0.0, (e.x - x1) / width))
            set_(int(round(lo + frac * (hi - lo))))
            draw()

        for it in (rail, fill, knob):
            c.tag_bind(it, "<Button-1>", move)
            c.tag_bind(it, "<B1-Motion>", move)
            c.tag_bind(it, "<Enter>", lambda _e: c.config(cursor="hand2"))
            c.tag_bind(it, "<Leave>", lambda _e: c.config(cursor=""))
        self._refreshers.append(draw)
        draw()

    # -- comandi ------------------------------------------------------------ #

    def open_durations(self):
        self.app.open_editor()

    @staticmethod
    def open_repo():
        try:
            webbrowser.open(REPO_URL)
        except Exception:
            pass

    def restore(self):
        self.app.restore_prefs()
        self.repaint()

    def close(self):
        self.app.prefs = None
        self.destroy()


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

class Focustime:

    def __init__(self):
        self.settings_path = self._settings_path()
        cfg = self._load_settings()

        self.theme_mode = cfg.get("theme", "dark")
        if self.theme_mode not in ("dark", "light", "auto"):
            self.theme_mode = "dark"
        self.opacity = self._clean_opacity(cfg.get("opacity", 100))
        use_palette(self._resolved_theme())

        self.root = tk.Tk()
        self.root.title("Focustime")
        self.root.overrideredirect(True)
        self.root.configure(bg=CHROMA)
        self.root.attributes("-transparentcolor", CHROMA)
        self.root.attributes("-topmost", bool(cfg.get("on_top", True)))

        self.on_top = tk.BooleanVar(value=bool(cfg.get("on_top", True)))
        self.sound_on = tk.BooleanVar(value=bool(cfg.get("sound", True)))
        self.notify_on = tk.BooleanVar(value=bool(cfg.get("notify", True)))
        self.auto_next = tk.BooleanVar(value=bool(cfg.get("auto_next", True)))
        self.about_on = tk.BooleanVar(value=bool(cfg.get("about", True)))
        self.startup = tk.BooleanVar(value=starts_with_windows())
        self.startup.trace_add("write", self._apply_startup)
        self._startup_busy = False
        self._save_job = None
        for var in (self.on_top, self.sound_on, self.notify_on,
                    self.auto_next, self.about_on):
            var.trace_add("write", self._save_soon)

        self.custom: dict[str, dict[str, int]] = {}
        raw = cfg.get("custom")
        if isinstance(raw, dict):
            keys = {t.key for t in TECHNIQUES}
            for k, v in raw.items():
                if k in keys and isinstance(v, dict):
                    self.custom[k] = {a: int(n) for a, n in v.items()
                                      if isinstance(n, (int, float))}

        keys = [t.key for t in TECHNIQUES]
        self.index = keys.index(cfg["technique"]) if cfg.get("technique") in keys else 0

        self.phase = "focus"          # focus | rest | long
        self.running = False
        self.completed = 0
        self.duration = 0.0
        self.left = 0.0               # secondi rimanenti (conto alla rovescia)
        self.up = 0.0                 # secondi trascorsi (Flowtime)
        self.end_at = 0.0
        self.start_at = 0.0
        self._toast: Toast | None = None
        self._about: About | None = None
        self._about_job = None
        self._tick_job = None
        self._ticks = 0
        self._hovered = None
        self._system_dark = system_prefers_dark()
        self.editor: Editor | None = None
        self.prefs: Prefs | None = None

        self._place_window(cfg.get("x"), cfg.get("y"))
        self._build_ui()
        self._menu()
        self._apply_opacity()
        self._enter_phase("focus", announce=False)
        self._tick()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<space>", lambda _e: self.toggle())
        self.root.bind("<Control-t>", lambda _e: self.flip_theme())
        self.root.bind("<Control-q>", lambda _e: self.quit())

    # -- persistenza -------------------------------------------------------- #

    @staticmethod
    def _settings_path() -> Path:
        return app_dir() / "settings.json"

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text("utf-8"))
        except Exception:
            return {}

    def _save_soon(self, *_args):
        """Salva fra poco.

        Ogni modifica finisce su disco subito, così una chiusura brutale (o lo
        spegnimento del PC) non porta via le impostazioni. Il rinvio evita di
        riscrivere il file quaranta volte mentre trascini il cursore.
        """
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(600, self._save_now)

    def _save_now(self):
        self._save_job = None
        self._save_settings()

    def _save_settings(self):
        data = {
            "technique": self.tech.key,
            "theme": self.theme_mode,
            "opacity": self.opacity,
            "on_top": self.on_top.get(),
            "sound": self.sound_on.get(),
            "notify": self.notify_on.get(),
            "auto_next": self.auto_next.get(),
            "about": self.about_on.get(),
            "custom": self.custom,
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        try:
            self.settings_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _place_window(self, x, y):
        """Rimette la finestra dove l'avevi lasciata, anche su un altro monitor.

        Se quel monitor non c'è più (portatile scollegato dal dock) torna in
        basso a destra sullo schermo principale.
        """
        if x is not None and y is not None:
            seen = on_a_monitor(x + W // 2, y + H // 2)
            if seen is None:      # senza Win32: controllo grossolano
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                seen = -W < x < sw and -H < y < sh
            if seen:
                self.root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")
                return
        _l, _t, right, bottom = work_area(self.root, 0, 0)
        self.root.geometry(f"{W}x{H}+{right - W - 40}+{bottom - H - 40}")

    # -- tema e opacità ----------------------------------------------------- #

    @staticmethod
    def _clean_opacity(value) -> int:
        try:
            return min(100, max(MIN_ALPHA, int(value)))
        except (TypeError, ValueError):
            return 100

    def _resolved_theme(self) -> str:
        if self.theme_mode == "auto":
            dark = self._system_dark if hasattr(self, "_system_dark") \
                else system_prefers_dark()
            return "dark" if dark is not False else "light"
        return self.theme_mode

    def set_theme_mode(self, mode: str):
        self.theme_mode = mode
        if mode == "auto":
            self._system_dark = system_prefers_dark()
        self.apply_theme()

    def flip_theme(self):
        """Un click: passa da chiaro a scuro e viceversa."""
        self.set_theme_mode("light" if self._resolved_theme() == "dark"
                            else "dark")
        if self.prefs is not None and self.prefs.winfo_exists():
            self.prefs.repaint()

    def apply_theme(self):
        use_palette(self._resolved_theme())
        self.skin.repaint()
        self.menu.config(bg=P["card"], fg=P["text"],
                         activebackground=P["focus"],
                         activeforeground=P["menu_text"])
        for panel in (self.prefs, self.editor, self._about, self._toast):
            if panel is not None and panel.winfo_exists():
                panel.repaint()
        if self._hovered is not None:
            self.c.itemconfig(self._hovered, fill=P["text"])
        self._render()
        self._save_soon()

    def set_opacity(self, value: int):
        self.opacity = self._clean_opacity(value)
        self._apply_opacity()
        self._save_soon()

    def _apply_opacity(self):
        try:
            self.root.attributes("-alpha", self.opacity / 100)
        except tk.TclError:
            pass

    def apply_on_top(self):
        self.root.attributes("-topmost", self.on_top.get())

    def _apply_startup(self, *_args):
        """Crea o toglie il collegamento senza congelare la finestra.

        Il collegamento lo costruisce PowerShell e ci mette quasi un secondo:
        farlo qui bloccherebbe il countdown, quindi va su un thread a parte.
        """
        if self._startup_busy:
            return
        wanted = bool(self.startup.get())

        def work():
            done = set_starts_with_windows(wanted)
            self.root.after(0, finish, done)

        def finish(done):
            if done != wanted:             # non è riuscito: rimetti la spunta
                self._startup_busy = True
                self.startup.set(done)
                self._startup_busy = False
            if self.prefs is not None and self.prefs.winfo_exists():
                self.prefs.repaint()

        threading.Thread(target=work, daemon=True).start()

    # -- interfaccia -------------------------------------------------------- #

    def _build_ui(self):
        c = tk.Canvas(self.root, width=W, height=H, bg=CHROMA,
                      highlightthickness=0)
        c.pack()
        self.c = c
        self.skin = Skin(c)

        self.skin.paint(rounded(c, 1, 1, W - 1, H - 1, 12, width=1),
                        fill="card", outline="border")

        self.i_emoji = c.create_text(20, 26, text="", font=FONT_EMOJI)
        self.skin.paint(self.i_emoji, fill="text")
        pad = self._hit(self.i_emoji, 20, 26, 26, self.cycle_technique)

        self.i_name = c.create_text(40, 27, text="", anchor="w", font=FONT_LABEL)
        self.i_name_pad = c.create_rectangle(0, 0, 0, 0, outline="")
        self.skin.paint(self.i_name_pad, fill="card")
        c.tag_lower(self.i_name_pad, self.i_name)
        for it in (self.i_name, self.i_name_pad, pad, self.i_emoji):
            c.tag_bind(it, "<Enter>", self._about_soon, add="+")
            c.tag_bind(it, "<Leave>", self._about_hide, add="+")
        c.tag_bind(self.i_name, "<Button-1>", lambda _e: self._about_now())
        c.tag_bind(self.i_name_pad, "<Button-1>", lambda _e: self._about_now())

        self.i_phase = c.create_text(W - 18, 27, text="", anchor="e",
                                     font=("Segoe UI Semibold", 9))
        self.i_time = c.create_text(W / 2, 68, text="00:00", font=FONT_TIME)

        self.dots = [c.create_oval(0, 0, 0, 0, outline="")
                     for _ in range(MAX_DOTS)]

        self.i_theme = self._button(152, 101, "◐", self.flip_theme)
        self.i_reset = self._button(178, 101, "↺", self.reset)
        self.i_skip = self._button(204, 101, "⏭", self.skip)
        self.i_play = self._button(230, 101, "▶", self.toggle)

        self.skin.paint(c.create_line(18, 117, W - 18, 117, width=3,
                                      capstyle="round"), fill="track")
        self.i_bar = c.create_line(18, 117, 18, 117, width=3, capstyle="round")

        self._drag = None
        c.bind("<Button-1>", self._press)
        c.bind("<B1-Motion>", self._motion)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<Double-Button-1>", self._double)
        c.bind("<Button-3>", self._popup)

    def _hit(self, item, cx, cy, size, action):
        """Area cliccabile invisibile sotto un item di testo."""
        r = size / 2
        pad = self.c.create_rectangle(cx - r, cy - r, cx + r, cy + r, outline="")
        self.skin.paint(pad, fill="card")
        self.c.tag_lower(pad, item)
        for it in (pad, item):
            self.c.tag_bind(it, "<Button-1>", lambda _e: self._arm(action))
            self.c.tag_bind(it, "<Enter>", lambda _e: self.c.config(cursor="hand2"))
            self.c.tag_bind(it, "<Leave>", lambda _e: self.c.config(cursor=""))
        return pad

    def _button(self, cx, cy, glyph, action):
        item = self.c.create_text(cx, cy, text=glyph, font=FONT_GLYPH)
        self.skin.paint(item, fill="muted")
        self._hit(item, cx, cy, 24, action)
        self.c.tag_bind(item, "<Enter>", lambda _e: self._hover(item, True))
        self.c.tag_bind(item, "<Leave>", lambda _e: self._hover(item, False))
        return item

    def _hover(self, item, on: bool):
        self._hovered = item if on else None
        self.c.itemconfig(item, fill=P["text"] if on else P["muted"])
        self.c.config(cursor="hand2" if on else "")

    # -- spiegazione della tecnica ------------------------------------------ #

    def _about_soon(self, _e=None):
        if not self.about_on.get() or self.editor is not None:
            return
        self._cancel_about_job()
        self._about_job = self.root.after(450, self._about_now)

    def _about_now(self):
        self._cancel_about_job()
        if not self.about_on.get() or self.editor is not None:
            return
        self._about_hide()
        self._about = About(self.root, self.tech, self.root.winfo_rootx(),
                            self.root.winfo_rooty(), W, H)

    def _about_hide(self, _e=None):
        self._cancel_about_job()
        if self._about is not None:
            if self._about.winfo_exists():
                self._about.destroy()
            self._about = None

    def _cancel_about_job(self):
        if self._about_job is not None:
            self.root.after_cancel(self._about_job)
            self._about_job = None

    # -- trascinamento e click ---------------------------------------------- #

    def _arm(self, action):
        """Un click su un comando non deve trascinare la finestra."""
        self._pending = action
        self._drag = None

    def _press(self, e):
        self.root.focus_force()          # così spazio e Ctrl+Q rispondono
        if getattr(self, "_pending", None):
            return
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _motion(self, e):
        if self._drag:
            self._about_hide()
            dx, dy = self._drag
            self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _release(self, _e):
        action = getattr(self, "_pending", None)
        moved = self._drag is not None
        self._pending = None
        self._drag = None
        if action:
            action()
        elif moved:
            self._save_soon()          # ricorda la nuova posizione

    def _double(self, _e):
        if not getattr(self, "_pending", None):
            self.toggle()

    def _menu(self):
        m = tk.Menu(self.root, tearoff=0, bg=P["card"], fg=P["text"],
                    activebackground=P["focus"], activeforeground=P["menu_text"],
                    bd=0, font=("Segoe UI", 9))
        m.add_command(label="Preferenze…", command=self.open_prefs)
        m.add_command(label="Personalizza le durate…", command=self.open_editor)
        m.add_separator()
        m.add_command(label="Azzera il ciclo", command=self.reset_cycle)
        m.add_command(label="Esci", command=self.quit)
        self.menu = m

    def _popup(self, e):
        self._about_hide()
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    # -- pannelli ----------------------------------------------------------- #

    def open_prefs(self):
        self._about_hide()
        if self.prefs is not None and self.prefs.winfo_exists():
            self.prefs.focus_force()
            return
        self.prefs = Prefs(self)

    def open_editor(self):
        self._about_hide()
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.focus_force()
            return
        self.editor = Editor(self)

    def restore_prefs(self):
        """Riporta le impostazioni ai valori di partenza (non le durate)."""
        self.theme_mode = "dark"
        self.opacity = 100
        self.on_top.set(True)
        self.auto_next.set(True)
        self.about_on.set(True)
        self.sound_on.set(True)
        self.notify_on.set(True)
        self.startup.set(False)
        self.apply_on_top()
        self._apply_opacity()
        self.apply_theme()

    # -- durate personalizzate ---------------------------------------------- #

    def apply_custom(self, values: dict[str, int]):
        """Salva le durate scelte per la tecnica corrente e le applica subito."""
        base = TECHNIQUES[self.index]
        diff = {a: n for a, n in values.items()
                if n != (getattr(base, a) // M if Editor._is_minutes(a)
                         else getattr(base, a))}
        if diff:
            self.custom[base.key] = diff
        else:
            self.custom.pop(base.key, None)
        self.running = False
        self._enter_phase(self.phase if self.phase != "long" or self.tech.long_rest
                          else "rest", announce=False)
        self._save_settings()

    # -- stato -------------------------------------------------------------- #

    @property
    def tech(self) -> Technique:
        base = TECHNIQUES[self.index]
        over = self.custom.get(base.key)
        if not over:
            return base
        fields = {}
        for attr, n in over.items():
            if not hasattr(base, attr):
                continue
            fields[attr] = n * M if Editor._is_minutes(attr) else n
        return replace(base, **fields) if fields else base

    @property
    def accent(self) -> str:
        return P["focus"] if self.phase == "focus" else P["rest"]

    @property
    def flowing(self) -> bool:
        return self.phase == "focus" and self.tech.focus == 0

    def _phase_label(self) -> str:
        if self.flowing:
            return "FLOW ↑"
        return {"focus": "FOCUS", "rest": "PAUSA", "long": "PAUSA LUNGA"}[self.phase]

    def _phase_seconds(self, phase: str) -> float:
        t = self.tech
        if phase == "focus":
            return t.focus
        if phase == "long":
            return t.long_rest or t.rest
        if t.ratio:  # Flowtime: la pausa dipende da quanto hai lavorato
            return min(t.max_rest, max(t.min_rest, self.up / t.ratio))
        return t.rest

    def _enter_phase(self, phase: str, announce: bool = True, auto: bool = False):
        self.phase = phase
        self.duration = self._phase_seconds(phase)
        self.left = self.duration
        self.up = 0.0
        self.running = auto and self.auto_next.get()
        now = time.monotonic()
        self.end_at = now + self.left
        self.start_at = now
        if announce:
            self._announce()
        self._render()

    def _announce(self):
        t = self.tech
        if self.phase == "focus":
            body = "Cronometro libero, fermalo quando esci dal flow" if self.flowing \
                else f"{int(self.duration // 60)} minuti di concentrazione"
            title = "Si riparte"
            tones = [(523, 110), (659, 140)]
        else:
            body = f"{int(self.duration // 60)} minuti di stacco"
            title = "Pausa lunga" if self.phase == "long" else "Pausa"
            tones = [(880, 110), (1046, 150)]
        if self.sound_on.get():
            beep(tones)
        if self.notify_on.get():
            if self._toast is not None and self._toast.winfo_exists():
                self._toast.destroy()
            self._toast = Toast(self.root, t.emoji, f"{t.name} · {title}",
                                body, "focus" if self.phase == "focus" else "rest")

    def _advance(self, auto: bool):
        if self.phase == "focus":
            self.completed += 1
            t = self.tech
            long_due = t.long_rest and t.cycle and self.completed % t.cycle == 0
            self._enter_phase("long" if long_due else "rest", auto=auto)
        else:
            self._enter_phase("focus", auto=auto)

    # -- comandi ------------------------------------------------------------ #

    def toggle(self):
        now = time.monotonic()
        if self.running:
            self.running = False
            if self.flowing:
                self.up = now - self.start_at
            else:
                self.left = max(0.0, self.end_at - now)
        else:
            self.running = True
            self.start_at = now - self.up
            self.end_at = now + self.left
        self._render()

    def reset(self):
        self.running = False
        self.left = self.duration
        self.up = 0.0
        self._render()

    def skip(self):
        if self.flowing and self.running:
            self.up = time.monotonic() - self.start_at
        self._advance(auto=True)

    def reset_cycle(self):
        self.completed = 0
        self._enter_phase("focus", announce=False)

    def cycle_technique(self):
        self._about_hide()
        self.index = (self.index + 1) % len(TECHNIQUES)
        self.completed = 0
        self._enter_phase("focus", announce=False)
        self._save_soon()

    def quit(self):
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        self._save_settings()
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        self._about_hide()
        for panel in (self.prefs, self.editor, self._toast):
            if panel is not None and panel.winfo_exists():
                panel.destroy()
        self.prefs = self.editor = self._toast = None
        self.root.destroy()

    # -- loop e disegno ----------------------------------------------------- #

    def _tick(self):
        if self.running:
            now = time.monotonic()
            if self.flowing:
                self.up = now - self.start_at
            else:
                self.left = self.end_at - now
                if self.left <= 0:
                    self.left = 0
                    self._advance(auto=True)
        self._ticks += 1
        if self.theme_mode == "auto" and self._ticks % 50 == 0:
            self._watch_system_theme()
        self._render()
        self._tick_job = self.root.after(100, self._tick)

    def _watch_system_theme(self):
        dark = system_prefers_dark()
        if dark is not None and dark != self._system_dark:
            self._system_dark = dark
            self.apply_theme()

    def _render(self):
        c, t = self.c, self.tech
        c.itemconfig(self.i_emoji, text=t.emoji)
        c.itemconfig(self.i_name, text=t.name, fill=P["muted"])
        c.coords(self.i_name_pad, *[v + d for v, d in
                                    zip(c.bbox(self.i_name), (-4, -4, 4, 4))])
        c.itemconfig(self.i_phase, text=self._phase_label(), fill=self.accent)
        c.itemconfig(self.i_time, fill=P["text"],
                     text=mmss(self.up if self.flowing else self.left))
        c.itemconfig(self.i_play, text="⏸" if self.running else "▶")

        if self.flowing:
            frac = min(self.up / (60 * M), 1.0)
        else:
            frac = 1 - (self.left / self.duration) if self.duration else 0.0
        x0, x1 = 18, W - 18
        frac = max(0.0, min(1.0, frac))
        c.coords(self.i_bar, x0, 117, x0 + frac * (x1 - x0), 117)
        c.itemconfig(self.i_bar, fill=self.accent,
                     state="hidden" if frac < 0.004 else "normal")

        slots = min(t.cycle if t.long_rest else 4, MAX_DOTS)
        done = self.completed % slots if self.completed else 0
        if self.completed and done == 0:
            done = slots
        for i, dot in enumerate(self.dots):
            if i >= slots:
                c.coords(dot, 0, 0, 0, 0)
                c.itemconfig(dot, fill="", outline="")
                continue
            x = 19 + i * 11
            c.coords(dot, x - 3, 98, x + 3, 104)
            c.itemconfig(dot, fill=self.accent if i < done else P["track"],
                         outline="")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Focustime().run()
