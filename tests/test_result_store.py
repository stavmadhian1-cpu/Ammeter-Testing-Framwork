import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.testing.ammeters import AMMETERS
from src.testing.result_store import ResultStore
from src.testing.results import AmmeterResult, SamplingSettings, TestRun


def sample_run() -> TestRun:
    settings = SamplingSettings.from_values(count=3, frequency=10)
    result = AmmeterResult(AMMETERS["entes"], settings, [(0.0, 50.0), (0.1, 60.0), (0.2, 70.0)],
                           ["Measurement 4: timed out"], max_delay=0.002, late_count=0)
    return TestRun(settings, datetime(2026, 11, 4, 12, 0, 0), 0.3, False, {"entes": result})


class ResultStoreTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = ResultStore(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_save_and_load_give_the_same_run(self):
        run = sample_run()
        folder = self.store.save(run, chart_png=b"png")
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["chart.png", "readings.csv", "report.txt", "run.json"])

        loaded = self.store.load(run.run_id)
        self.assertEqual(loaded.results["entes"].readings, run.results["entes"].readings)
        self.assertEqual(loaded.results["entes"].errors, run.results["entes"].errors)
        self.assertEqual(loaded.to_text(), run.to_text())
        self.assertIn(run.run_id, (Path(self.folder.name) / "index.csv").read_text(encoding="utf-8"))

    def test_delete_removes_the_run(self):
        run = sample_run()
        self.store.save(run)
        self.store.delete(run.run_id)
        self.assertEqual(self.store.list_runs(), [])
        with self.assertRaises(FileNotFoundError):
            self.store.load(run.run_id)

    def test_invalid_run_id_is_rejected(self):
        # A run ID must not be able to point outside the results folder
        for run_id in ("../../secret", "20261104_120000", ""):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                self.store.load(run_id)

    def test_damaged_run_is_skipped_and_reported(self):
        good, damaged = sample_run(), sample_run()
        self.store.save(good)
        (self.store.save(damaged) / "run.json").write_text("{ not json", encoding="utf-8")

        self.assertEqual([run["run_id"] for run in self.store.list_runs()], [good.run_id])
        with self.assertRaisesRegex(ValueError, "damaged"):
            self.store.load(damaged.run_id)


if __name__ == "__main__":
    unittest.main()
