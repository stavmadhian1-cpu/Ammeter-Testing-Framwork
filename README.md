# Ammeter Testing Framework

A testing framework for current measurement with three types of ammeters: **Greenlee**, **ENTES** and **CIRCUTOR**.
Each ammeter is emulated by a small TCP server. The framework measures them with configurable sampling, analyzes
the readings, saves every test run, and compares the ammeter types, all from one window.

> **Sample test results:** see [SAMPLE_RESULTS.md](SAMPLE_RESULTS.md). It lists the 8 sample runs in the
> [`results/`](results/) folder, what each one shows, and the comparison of the ammeters.

More documentation:

- [SAMPLE_RESULTS.md](SAMPLE_RESULTS.md): the sample test results and what they show.
- [DESIGN.md](DESIGN.md): the design decisions and the reasons for them.
- [FIXES.md](FIXES.md): the bugs that were fixed to make `main.py` work.
- [CHANGES.md](CHANGES.md): everything that was added after that, and why.
- [Exam/ammeter-test-specification.pdf](Exam/ammeter-test-specification.pdf): the task.

## Installation

Requirements:

- **Python 3.** Tested with Python 3.13 on Windows 11. Older versions from Python 3.9 should work, but were not tested.
- **Tkinter.** It comes with Python on Windows and macOS. On Linux, install it separately, for example
  `sudo apt install python3-tk`.
- **matplotlib 3.5 or newer.** It draws the charts. Tested with 3.11.2.

```sh
python -m pip install -r requirements.txt
```

`requirements.txt` lists only matplotlib, the one library the framework needs. Installing it also installs the
libraries matplotlib depends on, such as numpy and pillow.

## Running

Run from the project folder:

```sh
python main.py
```

This starts the three ammeter emulators (ports 5000, 5001 and 5002) and opens the measurement window.
Closing the window stops everything.

| Option | What it does |
|---|---|
| `--realistic` | Starts the emulators in realistic mode (see [Emulator modes](#emulator-modes)). It can also be switched in the window. |
| `--help` | Shows the options. |

## Using the window

The window has three tabs.

### 1. New test

1. **Sampling settings:** enter two of the three values. The value marked **Auto** is calculated from the
   other two (number of measurements = duration × frequency). Click another **Auto** button to choose which value
   is calculated.
   - **Number of measurements:** per ammeter.
   - **Total test duration:** in seconds.
   - **Sampling frequency:** measurements per second (Hz). Above 30 Hz a warning appears, because the emulators may
     not answer fast enough.
2. **Ammeters to test:** tick one or more ammeters. All the ticked ammeters are measured at the same time.
3. **Emulators:** tick **Realistic** to use realistic emulators.
4. Click **Start measurement**. The chart shows the readings live, one chart per ammeter. **Stop** ends the test
   early. The readings collected until then are kept.
5. When the test ends, the **Results** table shows for each ammeter: collected readings, errors, mean, median,
   standard deviation, min, max, the largest timing delay, and whether the timing was **OK** or **Late**.
   The same report is printed in the terminal. The run is saved automatically.

### 2. History

All saved runs, newest first.

- **Select one run** to see its chart and results.
- **Select several runs** (Ctrl+click or Shift+click) to compare them: a table of all results and a box plot per
  ammeter, one box per run.
- **Ammeter comparison** sub-tab: the ammeter types ranked by precision for the selected runs.
- **Open folder** opens the run's folder in the file manager. **Delete** deletes the selected runs, after asking.

### 3. Accuracy assessment

Compares the ammeter types over runs you choose.

1. **Pick runs** on the left: click a run to tick or untick it. **Show** filters the list by emulator mode.
   **Select all**, **Clear** and **Last N runs** select runs quickly.
2. The right side updates right away:
   - **Verdict:** the most reliable ammeter.
   - **One card per ammeter**, in rank order: mean, median, standard deviation, min / max, CV with its 95% range,
     success rate, run-to-run CV, timing and the largest delay. All readings of the selected runs are combined
     before calculating.
   - **Timing note:** if some selected runs had late measurements, an orange note at the top says how many.
     The **Timing** column in the runs list shows which runs were late.
   - **Four charts:**
     1. Precision: the CV per ammeter, with its 95% range.
     2. Spread: each reading divided by its ammeter's mean, so all ammeters share one scale.
     3. Consistency between runs: each run's average.
     4. Agreement: the range of the readings in amperes, on a log scale.
   - **Notes:** if the difference between the ammeters is statistically significant, and what the results can and
     can't tell about accuracy.
3. **Zoom into a chart:** drag a box on it, or scroll the mouse wheel. Double-click the chart to go back to the
   full view.

How the ammeters are ranked:

- First by **success rate** (readings received ÷ readings expected), then by the lowest
  **CV (coefficient of variation)** = standard deviation ÷ mean. A lower CV means steadier readings.
- An ammeter needs at least 10 readings to be ranked.
- The 95% range of the CV is found with a bootstrap: the readings are resampled 1,000 times. If the ranges of two
  ammeters don't overlap, the difference between them is significant.

**About accuracy:** the emulators don't have a known true current, so the framework measures **precision**
(how steady the readings are) and **agreement** between the ammeters. Real accuracy needs a calibrated current
source or a reference meter.

## Emulator modes

| Mode | Behavior |
|---|---|
| **Original** (default) | The emulators behave exactly as provided: each measurement picks new random values for everything, including the device constants. |
| **Realistic** | The device constants (Greenlee resistance, ENTES calibration factor, CIRCUTOR time step) are chosen once at the first measurement and stay the same until the program closes, like a real device. Only the measured quantity changes. |

The mode is saved with every run, and in realistic mode the device constants are saved too. Switching back to
realistic mode in the same session keeps the same constants.

## Results

The project includes 8 sample runs. [SAMPLE_RESULTS.md](SAMPLE_RESULTS.md) explains each one and the comparison
of the ammeters.

Every run is saved automatically in the `results/` folder:

```
results/
├── index.csv                    One line per run
└── runs/
    └── 20261103_142247_da3a/    One folder per run, named by its unique run ID
        ├── run.json             Metadata: start time, status, settings, environment, emulator mode,
        │                        and for each ammeter its port, command, statistics, timing and errors
        ├── readings.csv         Every measurement: ammeter, reading number, time (s), current (A)
        ├── chart.png            The chart at the end of the test
        └── report.txt           The text report: results table, ammeter comparison and notes
```

- The run ID is the date, the time and 4 random characters, so it is unique and sorts by date.
- The files are JSON and CSV, so they open in any text editor or in Excel.

## Using the framework from Python

The framework can also be used without the window. The emulators must be running, either from `main.py` in another
terminal, or started in the same script:

```python
import time

from main import Emulators
from src.testing.result_store import ResultStore
from src.testing.results import SamplingSettings
from src.testing.test_framework import AmmeterTestFramework

Emulators().start()
time.sleep(0.5)  # Give the emulators a moment to start listening

framework = AmmeterTestFramework()
settings = SamplingSettings.from_values(count=20, duration=2)  # Any two of: count, duration, frequency

result = framework.run_test("greenlee", settings)  # One ammeter
print(result.report_row())

run = framework.run_tests(["entes", "circutor"], settings)  # Several ammeters at the same time
print(run.to_text())
ResultStore().save(run)  # Saved in results/, like a run from the window
```

The ammeter types are `"greenlee"`, `"entes"` and `"circutor"`. Leaving out the list in `run_tests()` tests all three.

A ready-made example does the same from the command line. It uses the emulators of a running `main.py`, or starts
its own:

```sh
python examples/run_tests.py                              # 50 measurements at 10 Hz
python examples/run_tests.py --count 100 --frequency 20 --save
```

Every test also writes a log file to `results/logs/` (start, settings, a summary per ammeter, every failed
measurement and late timing). `AmmeterTestFramework(log_dir=None)` turns logging off.

## Running the tests

The `tests/` folder has automated tests, written with Python's built-in `unittest` (no extra library).
Run them from the project folder:

```sh
python -m unittest -v
```

They don't need the emulators or the window: the network tests use a small fake ammeter server, and the
result tests use a temporary folder, so `results/` is never changed.

| File | What it tests |
|---|---|
| `test_sampling_settings.py` | The third sampling value is calculated, values must match, invalid values are rejected |
| `test_analysis.py` | Statistics, timing text, ranking (success rate first, then CV, not ranked under 10 readings), bootstrap range |
| `test_result_store.py` | Save and load give the same run, delete, invalid run IDs are rejected, a damaged run is skipped |
| `test_measurement.py` | The client reads a current and raises clear errors, a test continues after failed measurements, the Greenlee output fix (FIXES.md, Fix 5) |

> **Note:** These tests were added at the end of the project. They run and pass, but I didn't have enough time to
> review each test in depth. With more time, I would check every test to verify that it is correct and tests the
> right behavior (for example, by breaking the code on purpose and checking that the test fails), and add more tests.

## Project structure

```
main.py                       Starts the emulators and opens the window
Ammeters/
  base_ammeter.py             Base class for the emulators: the TCP server and the realistic mode
  Greenlee_Ammeter.py         Greenlee emulator
  Entes_Ammeter.py            ENTES emulator
  Circutor_Ammeter.py         CIRCUTOR emulator
  client.py                   Sends a command to an emulator and reads the current
src/
  testing/
    ammeters.py               The ammeter types: name, port, command and measurement method
    test_framework.py         The unified testing interface: run_test() and run_tests()
    sampling.py               Timing and data collection
    results.py                Sampling settings, result format, statistics and the text report
    analysis.py               Comparing the ammeter types: CV, ranking, bootstrap and notes
    result_store.py           Saving, listing, loading and deleting runs in results/
  gui/
    measurement_app.py        The window and the "New test" tab
    history_tab.py            The "History" tab
    analysis_tab.py           The "Accuracy assessment" tab
    chart_view.py             Shows the charts in the window
  utils/
    logger.py                 Writes a log file for every test, in results/logs
    Utils.py                  Random numbers for the emulators
    config.py                 Reads config.yaml (not used yet)
config/
  config.yaml                 Configuration template, not used yet
examples/
  run_tests.py                Example: tests all ammeters without the window (see "Using the framework from Python")
tests/                        Automated tests (see "Running the tests")
results/                      Saved test runs and logs
Exam/                         The task specification
```

## The ammeters

| Ammeter | Port | Command | Measurement method | Calculation |
|---|---|---|---|---|
| Greenlee | 5000 | `MEASURE_GREENLEE -get_measurement` | Ohm's law: I = V / R | Voltage 1–10 V, resistance 0.1–100 Ω |
| ENTES | 5001 | `MEASURE_ENTES -get_data` | Hall effect: I = B × K | Magnetic field 0.01–0.1 T, calibration factor 500–2000 |
| CIRCUTOR | 5002 | `MEASURE_CIRCUTOR -get_measurement` | Rogowski coil integration: I = ∫V dt | Voltage samples 0.1–1.0 V, time step 0.001–0.01 s |

Each emulator answers only its exact command. Any other message gets no reply.

## Troubleshooting

| Problem | Cause and solution |
|---|---|
| `OSError: [WinError 10048]` or `Address already in use` | Another copy of `main.py` is still running and holds ports 5000–5002. Close it, or wait a few seconds and try again. |
| Errors like "connection refused" or "timed out" in the results | The emulator isn't running, or didn't answer within 2 seconds. Start the emulators with `main.py`. |
| Errors like "No data received" in the results | The emulator got a wrong command. Each emulator answers only its exact command (see [The ammeters](#the-ammeters)). |
| Timing shows **Late**, e.g. "Late 82/600 (13.7%)" | That many measurements were taken more than one interval after their planned time. The sampling frequency is too high for the emulators: use 30 Hz or less. |
| `ModuleNotFoundError: No module named 'matplotlib'` | Install it: `python -m pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'tkinter'` | Linux only: install Tkinter, for example `sudo apt install python3-tk`. |
