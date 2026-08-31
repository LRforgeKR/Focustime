import unittest

from techniques import M, TECHNIQUES


class TechniquesTests(unittest.TestCase):

    def test_technique_keys_are_unique(self):
        keys = [technique.key for technique in TECHNIQUES]

        self.assertEqual(len(keys), len(set(keys)))

    def test_pomodoro_defaults(self):
        pomodoro = next(
            technique
            for technique in TECHNIQUES
            if technique.key == "pomodoro"
        )

        self.assertEqual(pomodoro.focus, 25 * M)
        self.assertEqual(pomodoro.rest, 5 * M)
        self.assertEqual(pomodoro.long_rest, 15 * M)
        self.assertEqual(pomodoro.cycle, 4)

    def test_flowtime_uses_ratio(self):
        flowtime = next(
            technique
            for technique in TECHNIQUES
            if technique.key == "flowtime"
        )

        self.assertEqual(flowtime.focus, 0)
        self.assertEqual(flowtime.rest, 0)
        self.assertEqual(flowtime.ratio, 5)

    def test_expected_techniques_exist(self):
        keys = {technique.key for technique in TECHNIQUES}

        expected = {
            "pomodoro",
            "5217",
            "ultradian",
            "flowtime",
            "animedoro",
        }

        self.assertEqual(keys, expected)


if __name__ == "__main__":
    unittest.main()