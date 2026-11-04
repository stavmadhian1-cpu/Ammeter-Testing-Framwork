import csv
import json
import os
import re
import shutil
from pathlib import Path

from src.testing.analysis import comparison_text
from src.testing.results import TestRun

# The "results" folder in the project root, so results are saved in the same place from any working directory
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"

RUN_ID_PATTERN = re.compile(r"\d{8}_\d{6}_[0-9a-f]{4}")
READINGS_COLUMNS = ("ammeter", "reading", "time_s", "current_a")
INDEX_COLUMNS = ("run_id", "started_at", "status", "measurements", "duration_s", "frequency_hz", "ammeters",
                 "total_time_s")


class ResultStore:
    """
    Saves test runs to files and loads them back. Each run gets its own folder:

        results/
            index.csv                 One line per run, to see all runs at a glance
            runs/<run_id>/
                run.json              Metadata, settings, statistics and errors
                readings.csv          Every measurement: ammeter, reading number, time (s), current (A)
                chart.png             The chart at the end of the test (if given)
                report.txt            The text report: results table, ammeter comparison and notes
    """

    def __init__(self, results_dir=DEFAULT_RESULTS_DIR):
        self.results_dir = Path(results_dir)
        self.runs_dir = self.results_dir / "runs"

    def save(self, run: TestRun, chart_png: bytes = None) -> Path:
        """
        Saves the run and returns its folder. Raises OSError if the files can't be written.
        """
        folder = self._run_folder(run.run_id)
        folder.mkdir(parents=True, exist_ok=True)

        rows = [
            {"ammeter": ammeter_type, "reading": number, "time_s": seconds, "current_a": current}
            for ammeter_type, result in run.results.items()
            for number, (seconds, current) in enumerate(result.readings, start=1)
        ]
        _write_csv(folder / "readings.csv", READINGS_COLUMNS, rows)
        if chart_png:
            _write_file(folder / "chart.png", chart_png)
        self.write_report(run)
        # run.json is written last: a folder without it is an incomplete save and is skipped when listing runs
        _write_file(folder / "run.json", json.dumps(run.to_dict(), indent=2).encode("utf-8"))
        self._write_index()
        return folder

    def write_report(self, run: TestRun) -> Path:
        """
        Writes the run's text report (the same report printed in the terminal) to report.txt in its folder,
        and returns its path. Raises OSError if the file can't be written.
        """
        path = self._run_folder(run.run_id) / "report.txt"
        _write_file(path, (run.to_text() + "\n\n" + comparison_text([run]) + "\n").encode("utf-8"))
        return path

    def list_runs(self) -> list:
        """
        Returns the saved data (run.json) of every run, newest first. Folders that can't be read are skipped.
        """
        runs = []  # (start time from the ID, save time, run data)
        if not self.runs_dir.is_dir():
            return []
        for folder in self.runs_dir.iterdir():
            if not RUN_ID_PATTERN.fullmatch(folder.name):
                continue
            run_file = folder / "run.json"
            try:
                runs.append((folder.name[:15], run_file.stat().st_mtime,
                             json.loads(run_file.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
        # Runs that started in the same second are ordered by the time they were saved
        return [run for _, _, run in sorted(runs, key=lambda item: item[:2], reverse=True)]

    def load(self, run_id: str) -> TestRun:
        """
        Loads a saved run with all its readings.
        Raises FileNotFoundError if there is no such run, or ValueError if its files are damaged.
        """
        folder = self._run_folder(run_id)
        try:
            data = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(f"No saved run with the ID {run_id}")
        except ValueError as error:
            raise ValueError(f"The saved run {run_id} is damaged: run.json can't be read ({error})")

        readings = {}
        readings_file = folder / "readings.csv"
        try:
            if readings_file.exists():
                with open(readings_file, newline="", encoding="utf-8") as file:
                    for row in csv.DictReader(file):
                        readings.setdefault(row["ammeter"], []).append(
                            (float(row["time_s"]), float(row["current_a"])))
            return TestRun.from_dict(data, readings)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"The saved run {run_id} is damaged: {type(error).__name__} {error}")

    def chart_path(self, run_id: str) -> Path:
        return self._run_folder(run_id) / "chart.png"

    def delete(self, run_id: str):
        """
        Deletes a saved run. Raises FileNotFoundError if there is no such run.
        """
        folder = self._run_folder(run_id)
        if not folder.is_dir():
            raise FileNotFoundError(f"No saved run with the ID {run_id}")
        shutil.rmtree(folder)
        self._write_index()

    def _run_folder(self, run_id: str) -> Path:
        # Only real run IDs are accepted, so a bad ID can't point to a folder outside results/runs
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(f"'{run_id}' is not a valid run ID")
        return self.runs_dir / run_id

    def _write_index(self):
        """
        Rewrites index.csv from the saved runs, so it always matches the folders.
        """
        rows = []
        for run in self.list_runs():
            rows.append({
                "run_id": run["run_id"],
                "started_at": run["started_at"],
                "status": run["status"],
                "measurements": run["settings"]["count"],
                "duration_s": run["settings"]["duration_s"],
                "frequency_hz": run["settings"]["frequency_hz"],
                "ammeters": " ".join(result["ammeter"]["name"] for result in run["ammeters"].values()),
                "total_time_s": round(run["total_time_s"], 3),
            })
        self.results_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(self.results_dir / "index.csv", INDEX_COLUMNS, rows)


def _write_file(path: Path, content: bytes):
    """
    Writes to a temporary file first and then replaces the real one,
    so a crash while writing never leaves a half-written file.
    """
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_csv(path: Path, columns: tuple, rows: list):
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)
