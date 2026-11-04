import platform
import secrets
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from src.testing.ammeters import Ammeter

# The columns of every result report. The window table and the text report both use them,
# so results are reported the same way for every ammeter type.
REPORT_COLUMNS = ("Ammeter", "Collected", "Errors", "Mean (A)", "Median (A)", "Std dev (A)", "Min (A)", "Max (A)",
                  "Max delay (ms)", "Timing")


@dataclass(frozen=True)
class SamplingSettings:
    count: int        # Number of measurements per ammeter
    duration: float   # Total test duration in seconds
    frequency: float  # Measurements per second

    @property
    def interval(self) -> float:
        return 1 / self.frequency

    @classmethod
    def from_values(cls, count=None, duration=None, frequency=None) -> "SamplingSettings":
        """
        Creates the settings from at least two of the three values. The values are linked: count = duration * frequency,
        so a missing value is calculated from the other two. Raises ValueError with a message for the user.
        """
        values = {"number of measurements": count, "test duration": duration, "sampling frequency": frequency}
        for label, value in values.items():
            if value is not None and value <= 0:
                raise ValueError(f"The {label} must be greater than 0.")
        if list(values.values()).count(None) > 1:
            raise ValueError("Enter at least two of: number of measurements, test duration, sampling frequency.")

        if count is None:
            count = round(duration * frequency)
            if count < 1:
                raise ValueError("This duration and frequency give less than 1 measurement.")
        elif duration is None:
            duration = count / frequency
        elif frequency is None:
            frequency = count / duration
        elif round(duration * frequency) != count:
            raise ValueError(f"The values don't match: {duration:g} s * {frequency:g} Hz = "
                             f"{duration * frequency:g} measurements, not {count}.")
        if count != int(count):
            raise ValueError("The number of measurements must be a whole number.")
        return cls(int(count), duration, frequency)

    def describe(self) -> str:
        return f"{self.count} measurements, {self.duration:.6g} s, {self.frequency:.6g} Hz"

    def to_dict(self) -> dict:
        return {"count": self.count, "duration_s": self.duration, "frequency_hz": self.frequency,
                "interval_s": self.interval}

    @classmethod
    def from_dict(cls, data: dict) -> "SamplingSettings":
        return cls(data["count"], data["duration_s"], data["frequency_hz"])


@dataclass
class AmmeterResult:
    """
    The result of testing one ammeter. It has the same fields for every ammeter type.
    """
    ammeter: Ammeter
    settings: SamplingSettings
    readings: list = field(default_factory=list)  # (time from start in seconds, current in A)
    errors: list = field(default_factory=list)
    max_delay: float = 0.0                         # Largest delay from the planned measurement time, in seconds
    late_count: int = None                         # Measurements late by more than one interval (None: not known)

    @property
    def currents(self) -> list:
        return [current for _, current in self.readings]

    @property
    def attempted(self) -> int:
        """
        Measurements that were taken, successful or not (fewer than the settings' count if the test was stopped).
        """
        return len(self.readings) + len(self.errors)

    @property
    def timing_ok(self) -> bool:
        return self.max_delay <= self.settings.interval

    def timing_text(self) -> str:
        """
        "OK", or how many measurements were late, e.g. "Late 82/600 (13.7%)".
        """
        if self.timing_ok:
            return "OK"
        if self.late_count is None or not self.attempted:
            return "Late"
        return f"Late {self.late_count}/{self.attempted} ({100 * self.late_count / self.attempted:.1f}%)"

    def statistics(self) -> dict:
        """
        Returns mean, median, std_dev, min and max of the currents. Values that can't be calculated are None.
        """
        currents = self.currents
        if not currents:
            return {"mean": None, "median": None, "std_dev": None, "min": None, "max": None}
        return {
            "mean": statistics.mean(currents),
            "median": statistics.median(currents),
            "std_dev": statistics.stdev(currents) if len(currents) > 1 else None,
            "min": min(currents),
            "max": max(currents),
        }

    def report_row(self) -> dict:
        """
        Returns this result as text values for each of the REPORT_COLUMNS.
        """
        stats = self.statistics()
        return {
            "Ammeter": self.ammeter.name,
            "Collected": f"{len(self.readings)} / {self.settings.count}",
            "Errors": str(len(self.errors)),
            "Mean (A)": _format(stats["mean"]),
            "Median (A)": _format(stats["median"]),
            "Std dev (A)": _format(stats["std_dev"]),
            "Min (A)": _format(stats["min"]),
            "Max (A)": _format(stats["max"]),
            "Max delay (ms)": f"{self.max_delay * 1000:.2f}",
            "Timing": self.timing_text(),
        }

    def to_dict(self) -> dict:
        """
        Returns the result for saving, without the readings (they are saved separately in a CSV file).
        """
        return {
            "ammeter": self.ammeter.to_dict(),
            "collected": len(self.readings),
            "expected": self.settings.count,
            "statistics": self.statistics(),
            "max_delay_s": self.max_delay,
            "timing": "OK" if self.timing_ok else "Late",
            "late_readings": self.late_count,
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, data: dict, settings: SamplingSettings, readings: list) -> "AmmeterResult":
        # Runs saved before the late measurements were counted have no "late_readings"
        return cls(Ammeter.from_dict(data["ammeter"]), settings, list(readings), list(data["errors"]),
                   data["max_delay_s"], data.get("late_readings"))


def new_run_id(started_at: datetime) -> str:
    """
    Returns a unique ID for a test run: date, time and 4 random characters, e.g. "20261103_102200_a1b2".
    The random part keeps IDs unique even when two runs start in the same second, and the IDs sort by date.
    """
    return f"{started_at:%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"


def current_environment() -> dict:
    return {"python": platform.python_version(), "os": platform.platform()}


@dataclass
class TestRun:
    """
    The result of one test run on one or more ammeters, all with the same settings.
    """
    settings: SamplingSettings
    started_at: datetime
    total_time: float = 0.0
    stopped: bool = False
    results: dict = field(default_factory=dict)  # Ammeter type -> AmmeterResult
    run_id: str = ""                              # Created from `started_at` if not given
    environment: dict = field(default_factory=current_environment)
    setup: dict = field(default_factory=dict)     # Test setup details, e.g. {"emulator_mode": "realistic"}

    @property
    def emulator_mode(self) -> str:
        # Runs saved before the mode was recorded used the original emulators
        return self.setup.get("emulator_mode", "original")

    def __post_init__(self):
        if not self.run_id:
            self.run_id = new_run_id(self.started_at)

    def to_dict(self) -> dict:
        """
        Returns the run's metadata and results for saving, without the readings.
        """
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "status": "stopped" if self.stopped else "finished",
            "total_time_s": self.total_time,
            "settings": self.settings.to_dict(),
            "environment": self.environment,
            "setup": self.setup,
            "ammeters": {ammeter_type: result.to_dict() for ammeter_type, result in self.results.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, readings: dict) -> "TestRun":
        """
        Creates a run from saved data. `readings` is ammeter type -> list of (seconds, current).
        """
        settings = SamplingSettings.from_dict(data["settings"])
        results = {
            ammeter_type: AmmeterResult.from_dict(result, settings, readings.get(ammeter_type, []))
            for ammeter_type, result in data["ammeters"].items()
        }
        return cls(settings, datetime.fromisoformat(data["started_at"]), data["total_time_s"],
                   data["status"] == "stopped", results, data["run_id"], data.get("environment", {}),
                   data.get("setup", {}))

    def summary(self) -> str:
        status = f"Stopped by the user after {self.total_time:.3f} s." if self.stopped \
            else f"Test finished in {self.total_time:.3f} s."
        return f"{status}   Settings: {self.settings.describe()}"

    def report_rows(self) -> list:
        return [result.report_row() for result in self.results.values()]

    def errors(self) -> list:
        return [f"{result.ammeter.name} - {error}" for result in self.results.values() for error in result.errors]

    def to_text(self) -> str:
        """
        Returns the full report as a text table.
        """
        rows = self.report_rows()
        widths = {column: max([len(column)] + [len(row[column]) for row in rows]) for column in REPORT_COLUMNS}
        lines = [
            f"Test run {self.run_id}, started {self.started_at:%Y-%m-%d %H:%M:%S}, "
            f"{self.emulator_mode} emulators",
            self.summary(),
            "",
            "  ".join(column.ljust(widths[column]) for column in REPORT_COLUMNS),
            "  ".join("-" * widths[column] for column in REPORT_COLUMNS),
        ]
        lines += ["  ".join(row[column].ljust(widths[column]) for column in REPORT_COLUMNS) for row in rows]
        errors = self.errors()
        if errors:
            lines += ["", "Errors:"] + [f"  {error}" for error in errors]
        return "\n".join(lines)


def _format(value) -> str:
    return "-" if value is None else f"{value:.6g}"
