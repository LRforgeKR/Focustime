from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


LINK_NAME = "Focustime.lnk"
NO_WINDOW = 0x08000000


def startup_link() -> Path:
    """Percorso del collegamento nella cartella Esecuzione automatica."""
    base = os.environ.get("APPDATA", "")

    return (
        Path(base)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / LINK_NAME
    )


def starts_with_windows() -> bool:
    """True se il collegamento di avvio automatico esiste."""
    try:
        return startup_link().exists()
    except Exception:
        return False


def set_starts_with_windows(
    on: bool,
    *,
    source_file: Path | None = None,
    workdir: Path | None = None,
) -> bool:
    """Attiva o disattiva l'avvio automatico di Focustime."""

    link = startup_link()

    if not on:
        try:
            link.unlink(missing_ok=True)
        except OSError:
            pass

        return starts_with_windows()

    if getattr(sys, "frozen", False):
        # Versione compilata con PyInstaller:
        # il collegamento deve puntare direttamente all'EXE.
        target = Path(sys.executable)
        args = ""

        if workdir is None:
            workdir = target.resolve().parent

    else:
        # Versione eseguita dal sorgente Python.
        if source_file is None:
            return False

        source_file = source_file.resolve()

        exe = Path(sys.executable)
        quiet = exe.with_name("pythonw.exe")

        # pythonw evita la finestra del terminale all'avvio.
        target = quiet if quiet.exists() else exe
        args = f'"{source_file}"'

        if workdir is None:
            workdir = source_file.parent

    def q(value):
        """Escaping degli apici nelle stringhe PowerShell."""
        return str(value).replace("'", "''")

    script = (
        f"$s=(New-Object -ComObject WScript.Shell)."
        f"CreateShortcut('{q(link)}');"
        f"$s.TargetPath='{q(target)}';"
        f"$s.Arguments='{q(args)}';"
        f"$s.WorkingDirectory='{q(workdir)}';"
        f"$s.Description='Focustime';"
        f"$s.Save()"
    )

    try:
        link.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            creationflags=NO_WINDOW,
            timeout=20,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    except Exception:
        pass

    return starts_with_windows()