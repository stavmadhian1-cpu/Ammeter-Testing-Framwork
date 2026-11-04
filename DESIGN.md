# Design Decisions

This document explains how the ammeter testing framework is built and why.
For how to use it, see [README.md](README.md). For the full list of changes, see [CHANGES.md](CHANGES.md).

## 1. Architecture

The code is split into layers. Each layer uses only the layers below it.

```
 GUI            src/gui/            measurement_app.py · history_tab.py · analysis_tab.py · chart_view.py
                    │
 Framework      src/testing/        test_framework.py      run_test() / run_tests(): the unified API
                    │                sampling.py            timing and data collection
                    │                results.py             result format, statistics, text report
                    │                analysis.py            comparison, ranking, bootstrap, notes
                    │                result_store.py        saving and loading runs
                    │                ammeters.py            the ammeter types (port, command, method)
                    │
 Communication  Ammeters/client.py  one TCP request -> one current value
                    │
 Emulators      Ammeters/*.py       the provided emulators (one TCP server per ammeter)
```

**Why:** The testing logic doesn't depend on the window. Everything the window does can also be done from Python
(see the README), so the framework can be reused in scripts, automated tests or CI. The GUI only collects
settings and displays results.

## 2. Unified measurement API

| Decision | Reason |
|---|---|
| Every ammeter type is described by data: an `Ammeter` entry with type, name, port, command and method, in one table (`AMMETERS`) | All ammeters are measured the same way, only the port and command differ. Adding a fourth ammeter type is one new line (plus its emulator), and the window, charts and reports pick it up automatically. |
| One entry point: `AmmeterTestFramework.run_test(type, settings)` and `run_tests(types, settings)` | The caller doesn't need to know which ammeter it is talking to. |
| One result format for every ammeter: `AmmeterResult` (readings, errors, statistics, timing) | Results can be reported, saved and compared the same way, whatever the ammeter. |
| Ammeter types are selected by name, not case sensitive, with a clear error for unknown names | Easy to call, hard to misuse. |

## 3. Measurement sampling

| Decision | Reason |
|---|---|
| The user enters any **two** of number of measurements, duration and frequency; the third is calculated (count = duration × frequency) | The three values depend on each other. Asking for all three could give values that contradict each other. |
| Each measurement is scheduled from the **start time** (measurement *i* at start + *i* × interval), not from the previous measurement | Small delays don't add up, so the test doesn't drift over time. |
| `time.perf_counter()` for all timing | The most precise clock in Python, and it isn't affected by changes to the system clock. |
| One thread per ammeter, with a shared start time | All ammeters are measured at the same moments, so they can be compared fairly. |
| The delay of every measurement is recorded; a measurement more than one interval late counts as **late** | Timing problems are measured and reported, not hidden. The result shows how many readings were late, e.g. `Late 82/600 (13.7%)`. |
| A warning above 30 Hz, but no hard limit | In test runs, delays grew with the frequency: no late readings at 15-20 Hz, a few at 25 Hz, 4-23% at 50 Hz (see [SAMPLE_RESULTS.md](SAMPLE_RESULTS.md)). The real limit depends on how busy the computer is (one 28.6 Hz run had 9.5% late readings), so the user is warned but can still test higher frequencies, and every run reports how many readings were late. |

## 4. Error handling

| Decision | Reason |
|---|---|
| A failed measurement (timeout, refused connection, no data, invalid value) is recorded with its number and the test **continues** | One lost reading shouldn't end a whole test. The errors are shown in the results and saved. |
| Every request has a 2-second timeout | A stuck emulator can't freeze the test. |
| Specific exceptions: `OSError` for connection problems, `ValueError` for bad data or bad settings | The caller can handle each kind of problem in its own way. Unexpected errors are not caught silently. |
| Settings are checked before the test starts (missing values, 0, negative numbers, values that don't match) | Problems are found early, with a message the user understands. |
| Every test writes its own log file (`results/logs`), with errors as `ERROR` and late timing as `WARNING` | A record of what happened, even for a test that failed before it could be saved. It uses the provided `TestLogger`, finished (see FIXES.md, Fix 7). |
| Damaged result files are skipped when listing runs, and loading one gives a clear error | One damaged file doesn't break the History or the Accuracy assessment tabs. |

## 5. Result analysis

| Decision | Reason |
|---|---|
| Statistics with Python's built-in `statistics` module | Exact results, no extra library. |
| **CV (coefficient of variation = std dev ÷ mean)** is the measure of precision | The ammeters read very different currents (about 0.03 A vs 65 A). The standard deviation can't be compared between them, but the CV, a percentage, can. |
| Ranking: highest success rate first, then lowest CV. At least 10 readings to be ranked | An ammeter that loses measurements isn't reliable, however steady its readings are. With fewer than 10 readings the statistics are too uncertain. |
| 95% confidence interval of the mean, with Student's t values for small samples | Shows how precisely each average is known. |
| **Bootstrap** 95% range of the CV (1,000 resamples, fixed seed) | Shows whether the winner is really steadier or won by chance. It makes no assumption about the shape of the data (Greenlee's readings are very skewed). The fixed seed gives the same result every time. |
| Run-to-run CV (spread of the run averages) | Measures consistency between runs, separately from the spread inside a run. |
| The readings of all selected runs are combined before calculating | Each reading counts equally. The spread includes the differences between runs, which are part of reliability. |
| The tool says clearly that **true accuracy can't be measured** | The emulators have no known true current. Accuracy needs a calibrated reference, so the framework measures precision, consistency and agreement between ammeters, and says so in its notes. |

## 6. Result management

```
results/index.csv                         one line per run
results/runs/<run ID>/run.json            metadata, settings, environment, statistics, timing, errors
                     /readings.csv        every reading: ammeter, number, time, current
                     /chart.png           the chart at the end of the test
                     /report.txt          the text report
```

| Decision | Reason |
|---|---|
| Run ID = date + time + 4 random characters, e.g. `20261104_094825_dfa6` | Unique even if two runs start in the same second, readable, and sorts by date. |
| One folder per run, in JSON, CSV, PNG and text | Built into Python, readable in any editor or Excel, works on every operating system, no database needed. |
| Every file is written to a temporary file and then renamed; `run.json` is written last | A crash never leaves a half-written file. A folder without `run.json` is an incomplete save and is skipped. |
| `index.csv` is rebuilt from the run folders after every change | It always matches the folders, even if a folder was deleted by hand. |
| Only valid run IDs are accepted when loading or deleting | A wrong ID can't point to files outside the `results` folder. |
| The setup is saved with each run (emulator mode, device constants, Python version, operating system) | Results can be compared fairly, and repeated later under the same conditions. |

## 7. User interface

| Decision | Reason |
|---|---|
| **Tkinter** | Comes with Python, works on Windows, macOS and Linux, no extra library. |
| Three tabs: **New test**, **History**, **Accuracy assessment** | One tab per task: run a test, look back at saved runs, compare the ammeter types. |
| Sampling runs in a background thread and sends readings to the window through a queue | The window stays responsive during a test, and Tkinter is only used from its own thread. |
| Charts are drawn by matplotlib's Agg engine into a PNG image and shown in the window | Windows Application Control blocked matplotlib's Tk backend (a compiled DLL). The image approach works everywhere and looks the same. |
| The live chart is redrawn every 250 ms, only when new readings arrived, and Python switches threads more often (`sys.setswitchinterval`) | Drawing a chart holds Python's interpreter lock. Without these changes, measurements were 6-19 ms late. With them, about 1-2 ms. |
| Zoom (drag a box, mouse wheel, double-click to reset) built into `chart_view.py` | matplotlib's own zoom toolbar needs the blocked backend. A few huge readings can squash a chart, so zooming is needed to see the details. |
| In the Accuracy assessment tab, runs are picked by hand, with a filter and quick-select buttons | The user decides exactly which runs to compare. Warnings appear for mixed emulator modes, mixed settings or late runs. |

## 8. Emulators

| Decision | Reason |
|---|---|
| The provided emulators are kept as they are; only the bugs needed to run them were fixed (see [FIXES.md](FIXES.md)) | The task asks to use the existing emulation infrastructure. |
| An optional **realistic mode** (`--realistic` or a check box): device constants (Greenlee resistance, ENTES calibration factor, CIRCUTOR time step) are chosen once per session | In the original emulators these constants change on every reading, which a real device doesn't do. Realistic mode gives more meaningful comparisons. It is off by default, so the original behavior stays the reference. The mode is saved with every run. |

## 9. Dependencies and portability

- **One external library: matplotlib** (`requirements.txt`). Everything else (Tkinter, `statistics`, `json`, `csv`,
  `socket`, `threading`) is built into Python. The task asks to minimize external dependencies.
- **Cross-platform:** paths use `pathlib`, all files are UTF-8, the results folder is found from the code's location
  (not the current directory), and "Open folder" uses the right command for Windows, macOS and Linux.

## 10. Automated tests

| Decision | Reason |
|---|---|
| Tests with Python's built-in `unittest`, run with `python -m unittest` | No extra library, works everywhere. |
| A few focused tests (19) on the logic that matters most: sampling settings, statistics and ranking, saving and loading, communication and error handling | They cover the parts where a bug would give wrong results or lose data, and stay fast (about 1 second). |
| A fake ammeter server on a free port, and a temporary results folder | The tests don't need the emulators, don't conflict with a running `main.py`, and never change `results/`. |
| A regression test for every fixed bug where it is practical (the Greenlee output, Fix 5) | A fixed bug must not come back. This test was checked to fail with the original code. |
| The window itself is not unit tested | The GUI only displays what the tested modules calculate. It was checked by running it. |

## 11. Known limitations

- **Emulator speed:** each measurement opens a new TCP connection, and the emulators print every reading to the
  terminal. This limits reliable sampling to about 30 Hz. The emulators were not changed to stay close to the
  provided infrastructure.
- **Accuracy:** without a reference current, only relative accuracy (agreement between the ammeters) can be judged.
- **Configuration file:** settings are entered in the window. `config/config.yaml` is not used yet (it would need
  the `pyyaml` library).
- **Analysis speed:** the Accuracy assessment is calculated in the window's thread. With thousands of readings
  selected, the window can pause for about a second.
