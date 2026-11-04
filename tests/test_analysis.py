import unittest
from datetime import datetime

from src.testing.ammeters import AMMETERS
from src.testing.analysis import bootstrap_cv_interval, compare_ammeters
from src.testing.results import AmmeterResult, SamplingSettings, TestRun

SETTINGS = SamplingSettings.from_values(count=20, frequency=10)


def result(ammeter_type: str, currents: list, **fields) -> AmmeterResult:
    readings = [(i * SETTINGS.interval, current) for i, current in enumerate(currents)]
    return AmmeterResult(AMMETERS[ammeter_type], SETTINGS, readings, **fields)


class StatisticsTest(unittest.TestCase):

    def test_statistics(self):
        stats = result("greenlee", [1.0, 2.0, 3.0, 4.0]).statistics()
        self.assertEqual(stats["mean"], 2.5)
        self.assertEqual(stats["median"], 2.5)
        self.assertAlmostEqual(stats["std_dev"], 1.290994, places=6)
        self.assertEqual((stats["min"], stats["max"]), (1.0, 4.0))

    def test_no_readings_give_no_statistics(self):
        self.assertEqual(set(result("greenlee", []).statistics().values()), {None})

    def test_timing_text(self):
        # Late means a delay longer than one interval (0.1 s here)
        on_time = result("greenlee", [1.0] * 10, max_delay=0.05, late_count=0)
        late = result("greenlee", [1.0] * 10, max_delay=0.2, late_count=3)
        not_counted = result("greenlee", [1.0] * 10, max_delay=0.2)  # Saved before late readings were counted
        self.assertEqual(on_time.timing_text(), "OK")
        self.assertEqual(late.timing_text(), "Late 3/10 (30.0%)")
        self.assertEqual(not_counted.timing_text(), "Late")


class ComparisonTest(unittest.TestCase):

    def test_steadiest_ammeter_ranks_first(self):
        run = TestRun(SETTINGS, datetime.now(), results={
            "greenlee": result("greenlee", [1, 5, 1, 5] * 5),                  # CV about 51%
            "entes": result("entes", [100, 101, 99, 100] * 5),                 # CV about 0.7%
            "circutor": result("circutor", [0.03, 0.03, 0.04]),               # Too few readings to rank
        })
        comparisons = compare_ammeters([run])
        self.assertEqual([c.ammeter.type for c in comparisons], ["entes", "greenlee", "circutor"])
        self.assertEqual([c.rank for c in comparisons], [1, 2, None])

    def test_success_rate_ranks_before_cv(self):
        # ENTES is steadier, but lost half its measurements
        run = TestRun(SETTINGS, datetime.now(), results={
            "greenlee": result("greenlee", [1, 2] * 10),
            "entes": result("entes", [100, 101] * 5, errors=["timed out"] * 10),
        })
        self.assertEqual(compare_ammeters([run])[0].ammeter.type, "greenlee")

    def test_bootstrap_range_contains_cv_and_is_repeatable(self):
        currents = [1, 2, 3, 4, 5] * 10
        low, high = bootstrap_cv_interval(currents)
        cv = compare_ammeters([TestRun(SETTINGS, datetime.now(), results={"greenlee": result("greenlee", currents)})])[0].cv
        self.assertLess(low, cv)
        self.assertLess(cv, high)
        self.assertEqual(bootstrap_cv_interval(currents), (low, high))  # Fixed seed: same result every time
        self.assertIsNone(bootstrap_cv_interval([1, 2, 3]))            # Too few readings


if __name__ == "__main__":
    unittest.main()
