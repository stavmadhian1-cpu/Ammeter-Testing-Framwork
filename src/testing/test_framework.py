import threading

from src.testing.ammeters import AMMETERS, get_ammeter
from src.testing.results import AmmeterResult, SamplingSettings, TestRun
from src.testing.sampling import run_sampling
from src.utils.logger import DEFAULT_LOG_DIR, TestLogger


class AmmeterTestFramework:
    """
    Unified interface to test any ammeter type. Every ammeter is tested with the same settings
    and returns its result in the same format (AmmeterResult), so results can be reported and compared the same way.
    Every test is logged to its own file in results/logs.

    Example:
        framework = AmmeterTestFramework()
        settings = SamplingSettings.from_values(count=20, duration=4)
        print(framework.run_test("greenlee", settings).report_row())
        print(framework.run_tests(["entes", "circutor"], settings).to_text())
    """

    def __init__(self, setup: dict = None, log_dir=DEFAULT_LOG_DIR):
        """
        setup: details of the test setup, saved with every test run, e.g. {"emulator_mode": "realistic"}.
        log_dir: the folder for the log files, or None to not write logs.
        """
        self.setup = dict(setup or {})
        self.log_dir = log_dir

    @staticmethod
    def available_types() -> list:
        return list(AMMETERS)

    def run_test(self, ammeter_type: str, settings: SamplingSettings, stop_event: threading.Event = None,
                 on_reading=None) -> AmmeterResult:
        """
        Tests one ammeter type, e.g. "greenlee". Raises ValueError for an unknown type.
        """
        run = self.run_tests([ammeter_type], settings, stop_event, on_reading)
        return run.results[get_ammeter(ammeter_type).type]

    def run_tests(self, ammeter_types: list = None, settings: SamplingSettings = None,
                  stop_event: threading.Event = None, on_reading=None) -> TestRun:
        """
        Tests several ammeter types at the same time, with the same settings. Tests all types if none are given.
        `on_reading(ammeter_type, seconds, current)` is called after every measurement, e.g. for a live chart.
        Raises ValueError for an unknown type, an empty list or missing settings.
        """
        if settings is None:
            raise ValueError("Sampling settings are required.")
        ammeter_types = self.available_types() if ammeter_types is None else ammeter_types
        if not ammeter_types:
            raise ValueError("Select at least one ammeter to test.")
        ammeters = list({get_ammeter(ammeter_type).type: get_ammeter(ammeter_type)
                         for ammeter_type in ammeter_types}.values())

        logger = TestLogger("_".join(ammeter.type for ammeter in ammeters), self.log_dir) if self.log_dir else None
        try:
            if logger:
                logger.info(f"Test started: {', '.join(ammeter.name for ammeter in ammeters)}, {settings.describe()}, "
                            f"setup {self.setup}")
            try:
                run = run_sampling(ammeters, settings, stop_event, on_reading)
            except Exception as error:
                if logger:
                    logger.error(f"Test failed: {type(error).__name__}: {error}")
                raise
            run.setup = dict(self.setup)
            if logger:
                _log_run(logger, run)
            return run
        finally:
            if logger:
                logger.close()


def _log_run(logger: TestLogger, run: TestRun):
    """
    Logs the result of a test run: one line per ammeter, every error, and late timing as a warning.
    """
    logger.info(f"Run ID {run.run_id}: {run.summary()}")
    for result in run.results.values():
        stats = result.statistics()
        mean = "-" if stats["mean"] is None else f"{stats['mean']:.6g} A"
        logger.info(f"{result.ammeter.name}: collected {len(result.readings)}/{result.settings.count}, "
                    f"{len(result.errors)} errors, mean {mean}, max delay {result.max_delay * 1000:.2f} ms, "
                    f"timing {result.timing_text()}")
        for error in result.errors:
            logger.error(f"{result.ammeter.name} - {error}")
        if not result.timing_ok:
            logger.warning(f"{result.ammeter.name}: late measurements, {result.timing_text()}")
    if run.stopped:
        logger.warning("The test was stopped before the end.")
    logger.info("Test finished.")
