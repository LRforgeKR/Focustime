from __future__ import annotations

import time
from collections.abc import Callable

from techniques import Technique


class TimerEngine:
    """Logica del timer, indipendente dall'interfaccia grafica."""

    def __init__(
        self,
        technique: Technique,
        *,
        auto_next: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.technique = technique
        self.auto_next = auto_next
        self._clock = clock

        self.phase = "focus"
        self.running = False
        self.completed = 0

        self.duration = 0.0
        self.left = 0.0
        self.up = 0.0

        self.end_at = 0.0
        self.start_at = 0.0

        self.enter_phase("focus")

    @property
    def flowing(self) -> bool:
        """True quando la tecnica usa il cronometro Flowtime."""
        return self.phase == "focus" and self.technique.focus == 0

    def phase_seconds(self, phase: str) -> float:
        """Restituisce la durata della fase richiesta."""
        t = self.technique

        if phase == "focus":
            return t.focus

        if phase == "long":
            return t.long_rest or t.rest

        if t.ratio:
            # Flowtime: pausa proporzionale al tempo lavorato.
            return min(
                t.max_rest,
                max(t.min_rest, self.up / t.ratio),
            )

        return t.rest

    def enter_phase(self, phase: str, *, auto: bool = False) -> None:
        """Passa a una nuova fase e ne inizializza lo stato."""
        self.phase = phase
        self.duration = self.phase_seconds(phase)
        self.left = self.duration
        self.up = 0.0

        self.running = auto and self.auto_next

        now = self._clock()
        self.end_at = now + self.left
        self.start_at = now

    def advance(self, *, auto: bool = False) -> None:
        """Passa alla fase successiva."""
        if self.phase == "focus":
            self.completed += 1

            t = self.technique
            long_due = (
                t.long_rest
                and t.cycle
                and self.completed % t.cycle == 0
            )

            self.enter_phase(
                "long" if long_due else "rest",
                auto=auto,
            )
        else:
            self.enter_phase("focus", auto=auto)

    def toggle(self) -> None:
        """Avvia o mette in pausa il timer."""
        now = self._clock()

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

    def reset(self) -> None:
        """Riporta la fase corrente all'inizio."""
        self.running = False
        self.left = self.duration
        self.up = 0.0

    def skip(self) -> None:
        """Salta alla fase successiva."""
        if self.flowing and self.running:
            self.up = self._clock() - self.start_at

        self.advance(auto=True)

    def reset_cycle(self) -> None:
        """Azzera il numero di focus completati."""
        self.completed = 0
        self.enter_phase("focus")

    def tick(self) -> bool:
        """
        Aggiorna il tempo.

        Restituisce True se il tick ha provocato
        automaticamente un cambio di fase.
        """
        if not self.running:
            return False

        now = self._clock()

        if self.flowing:
            self.up = now - self.start_at
            return False

        self.left = self.end_at - now

        if self.left <= 0:
            self.left = 0.0
            self.advance(auto=True)
            return True

        return False

    def set_technique(self, technique: Technique) -> None:
        """Cambia tecnica e riparte dal focus."""
        self.technique = technique
        self.completed = 0
        self.enter_phase("focus")