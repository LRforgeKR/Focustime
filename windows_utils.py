from __future__ import annotations

try:
    import ctypes
except ImportError:
    ctypes = None


NEAREST = 2
NONE = 0


if ctypes is not None:
    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class _POINT(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", _RECT),
            ("rcWork", _RECT),
            ("dwFlags", ctypes.c_ulong),
        ]


def _monitor(x, y, flag):
    if ctypes is None or not hasattr(ctypes, "windll"):
        return None

    try:
        return ctypes.windll.user32.MonitorFromPoint(
            _POINT(int(x), int(y)),
            flag,
        )
    except Exception:
        return None


def work_area(widget, x, y) -> tuple[int, int, int, int]:
    """Area utile del monitor che contiene il punto x, y."""
    h = _monitor(x, y, NEAREST)

    if h:
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)

        try:
            if ctypes.windll.user32.GetMonitorInfoW(
                h,
                ctypes.byref(mi),
            ):
                r = mi.rcWork
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass

    return (
        0,
        0,
        widget.winfo_screenwidth(),
        widget.winfo_screenheight(),
    )


def on_a_monitor(x, y) -> bool | None:
    """Restituisce True se il punto è dentro uno schermo collegato."""
    if ctypes is None or not hasattr(ctypes, "windll"):
        return None

    return bool(_monitor(x, y, NONE))


def system_prefers_dark() -> bool | None:
    """Restituisce True se Windows usa il tema scuro."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )

        with key:
            light, _ = winreg.QueryValueEx(
                key,
                "AppsUseLightTheme",
            )

        return not bool(light)

    except Exception:
        return None