import unittest

from techniques import M, TECHNIQUES
from timer_engine import TimerEngine


class FakeClock:
    """Orologio controllabile usato soltanto nei test."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def technique(key):
    return next(t for t in TECHNIQUES if t.key == key)


class TimerEngineTests(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock()

    def test_initial_pomodoro_state(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        self.assertEqual(engine.phase, "focus")
        self.assertFalse(engine.running)
        self.assertEqual(engine.left, 25 * M)
        self.assertEqual(engine.completed, 0)

    def test_countdown_uses_elapsed_time(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        engine.toggle()

        self.clock.advance(10)
        engine.tick()

        self.assertEqual(engine.left, 25 * M - 10)

    def test_pause_and_resume_preserve_remaining_time(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        engine.toggle()

        self.clock.advance(100)
        engine.tick()

        engine.toggle()

        remaining = engine.left

        self.clock.advance(500)

        # Essendo in pausa, il tempo non deve diminuire.
        engine.tick()

        self.assertEqual(engine.left, remaining)

        engine.toggle()

        self.clock.advance(20)
        engine.tick()

        self.assertEqual(engine.left, remaining - 20)

    def test_focus_finishes_into_rest(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        engine.toggle()

        self.clock.advance(25 * M)
        phase_changed = engine.tick()

        self.assertTrue(phase_changed)
        self.assertEqual(engine.phase, "rest")
        self.assertEqual(engine.completed, 1)
        self.assertEqual(engine.left, 5 * M)

    def test_fourth_pomodoro_uses_long_rest(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        for _ in range(3):
            engine.advance()
            self.assertEqual(engine.phase, "rest")
            engine.advance()
            self.assertEqual(engine.phase, "focus")

        engine.advance()

        self.assertEqual(engine.completed, 4)
        self.assertEqual(engine.phase, "long")
        self.assertEqual(engine.left, 15 * M)

    def test_reset_restores_current_phase(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        engine.toggle()
        self.clock.advance(200)
        engine.tick()

        engine.reset()

        self.assertFalse(engine.running)
        self.assertEqual(engine.left, 25 * M)

    def test_flowtime_counts_up(self):
        engine = TimerEngine(
            technique("flowtime"),
            clock=self.clock,
        )

        engine.toggle()

        self.clock.advance(30 * M)
        engine.tick()

        self.assertEqual(engine.up, 30 * M)

    def test_flowtime_rest_is_proportional(self):
        engine = TimerEngine(
            technique("flowtime"),
            clock=self.clock,
        )

        engine.toggle()

        self.clock.advance(50 * M)
        engine.skip()

        self.assertEqual(engine.phase, "rest")

        # 50 minuti / rapporto 5 = 10 minuti di pausa.
        self.assertEqual(engine.duration, 10 * M)

    def test_reset_cycle(self):
        engine = TimerEngine(
            technique("pomodoro"),
            clock=self.clock,
        )

        engine.advance()
        engine.advance()
        engine.advance()

        self.assertGreater(engine.completed, 0)

        engine.reset_cycle()

        self.assertEqual(engine.completed, 0)
        self.assertEqual(engine.phase, "focus")


if __name__ == "__main__":
    unittest.main()