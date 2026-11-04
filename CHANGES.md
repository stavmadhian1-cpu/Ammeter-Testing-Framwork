# Project Changes

This file explains the changes made to the project after `main.py` started working, and why each change was made.
The bug fixes that made `main.py` work are described in `FIXES.md`.

## How to run

```sh
python main.py
```

A window opens. Realistic emulators (fixed device constants, see section 11) can be turned on with a check box
in the window, or when starting the program: `python main.py --realistic`. Enter the sampling settings, choose the ammeters, and click **Start measurement**.

## 1. Sampling settings in a window

**What changed:** Before, `main.py` took only one measurement from each ammeter. Now a window opens and the user sets:

- Number of measurements
- Total test duration (seconds)
- Sampling frequency (measurements per second, Hz)

These three values are linked: **number of measurements = duration x frequency**.
For example, 2 seconds at 5 Hz gives 10 measurements. So the user enters only two values, and the third one
(marked **Auto**) is calculated automatically. The user can choose which value is calculated.

**Why:** The task asks for configurable sampling (number of measurements, test duration, sampling frequency).
Asking for all three values could give values that don't match, so the program calculates the third one instead.

**Input checks:** The window shows a red message and disables the Start button when the input is wrong
(text instead of a number, 0, a negative number, or a missing value). Above 30 Hz it shows an orange warning,
because the ammeters may not answer that fast (see "The ammeters have a speed limit" below).

## 2. Accurate timing

**What changed:** Each measurement is planned from the start of the test: measurement number *i* is taken at
*start time + i x interval*.

**Why:** If each measurement waited a fixed time after the previous one, small delays would add up and the test
would slowly drift. Planning every measurement from the start time keeps the test on time from beginning to end.

Other timing details:

- All selected ammeters are measured at the same moments, each in its own thread.
- The program uses `time.perf_counter()`, the most precise clock in Python.
- The test always lasts the full duration the user entered.
- The program records how late each measurement was. In tests, the delay was usually 1-2 ms.
  A measurement later than one full interval counts as late. The result shows **OK** if no measurement was late,
  or how many were late, for example **Late 82/600 (13.7%)**. The number of late measurements is saved
  in `run.json` (`late_readings`).

## 3. Live chart during the measurement

**What changed:** During the test, the window shows a chart for each ammeter that updates while measurements come in.
There is also a progress bar and a **Stop** button to end the test early.

**Why:** The user can see the measurements as they happen and doesn't have to wait for the end of the test.
Each ammeter has its own chart because their values are very different
(for example, ENTES gives about 10-200 A and CIRCUTOR about 0.01-0.06 A). On one shared chart,
the small values would look like a flat line.

## 4. Results with statistics

**What changed:** When the test ends, a results table shows for each ammeter:

| Column | Meaning |
|---|---|
| Collected | Measurements received out of the planned number |
| Errors | Measurements that failed |
| Mean, Median | Average and middle value of the current |
| Std dev | Standard deviation: how much the values spread |
| Min, Max | Smallest and largest value |
| Max delay (ms) | The latest a measurement was taken compared to its planned time |
| Timing | OK, or how many measurements were late by more than one interval, e.g. Late 82/600 (13.7%) |

The same report is also printed as text in the terminal, and the results are saved to files (see section 8).

**Why:** The task asks for the mean, median, standard deviation, minimum and maximum.
The timing columns show if the test kept the requested sampling frequency.

## 5. One testing interface for all ammeters

**What changed:** All three ammeters (Greenlee, ENTES, CIRCUTOR) are tested through the same code:

```python
framework = AmmeterTestFramework()
settings = SamplingSettings.from_values(count=20, duration=4)   # frequency is calculated
framework.run_test("greenlee", settings)                          # one ammeter
framework.run_tests(["entes", "circutor"], settings)              # several ammeters
framework.run_tests(settings=settings)                            # all ammeters
```

In the window, the user chooses the ammeters with check boxes.

**Why:** The task asks for a unified testing interface that works with multiple ammeter types.
Each ammeter is described once (name, port, command, measurement method) in `src/testing/ammeters.py`,
so adding a new ammeter type means adding one line there.
An unknown ammeter type gives a clear error message.

## 6. The same result format for every ammeter

**What changed:** Every ammeter's result has the same fields (`AmmeterResult`), and every test run is saved
in the same structure (`TestRun`). There is one list of report columns, used by both the window table
and the text report.

**Why:** The task asks for consistent result reporting. With one shared format, results of different ammeters
can be compared, and the window and the text report always show the same information.

## 7. Error handling

**What changed:** If an ammeter doesn't answer, answers too slowly (more than 2 seconds), or sends an empty answer,
the measurement is counted as an error and the test continues. The errors are listed under the results table.

**Why:** One failed measurement should not stop the whole test or crash the program.

## 8. Saving the results

**What changed:** Every test run is saved automatically when it ends, including runs stopped by the user.
Each run gets its own folder in `results/`:

```
results/
├── index.csv                     One line per run: a quick list of all runs
└── runs/
    └── 20261103_102200_a1b2/     One folder per run, named by the run ID
        ├── run.json              Metadata, settings, statistics and errors
        ├── readings.csv          Every measurement: ammeter, reading number, time (s), current (A)
        ├── chart.png             The chart at the end of the test
        └── report.txt            The text report: results table, ammeter comparison and notes
```

- **Unique ID:** date + time + 4 random characters, for example `20261103_102200_a1b2`.
  It stays unique even if two runs start in the same second, and the folders sort by date.
- **Metadata in `run.json`:** run ID, start time, status (finished or stopped), total test time, settings,
  Python version and operating system, and for each ammeter: port, command, measurement method,
  collected measurements, statistics, timing and errors.
- **Loading:** a saved run can be loaded back with all its readings (`ResultStore.load(run_id)`),
  and it gives exactly the same results and report as when it ran.
- **Text report in `report.txt`:** the same report that is printed in the terminal at the end of the test
  (results table, ammeter comparison and notes). It is written for every run, from the window or from Python,
  so each run can be read or shared without running the program. A run saved before this change can get its
  `report.txt` with `ResultStore.write_report()`.

**Why:** The task asks for a result archiving system with a unique ID for each test run, metadata storage,
and easy retrieval and comparison of past results.

- JSON and CSV are built into Python, so no new library is needed, and they work on every operating system.
- People can read them in any text editor, and the CSV files open in Excel.
- `index.csv` gives a quick list of all runs without opening each folder.

**Safety:**

- Files are first written to a temporary file and then renamed, so a crash never leaves a half-written file.
- A damaged run folder is skipped when listing runs, and loading it gives a clear error message.
- Only real run IDs are accepted, so a wrong ID can't point to files outside the `results` folder.

## 9. History tab: viewing and comparing saved runs

**What changed:** The window now has two tabs:

- **New test** - the measurement screen described above.
- **History** - a list of all saved runs (newest first) with their date, status, settings, ammeters and total time.

In the History tab:

- **Select one run** to see its chart and results table, the same as when the test ran.
- **Select several runs** (Ctrl+click or Shift+click) to compare them:
  - A table with the results of every ammeter in every selected run.
  - A **box plot** for each ammeter, with one box per run. The box shows where most of the values are,
    the line inside it is the median, the triangle is the mean, and the circles are unusual values (outliers).
    If an ammeter was not tested in a run, the chart says "not tested".
  - A note if the runs used different settings, because then the comparison is less fair.
- **Open folder** opens the selected run's folder (or the `results` folder) in the file manager.
- **Delete** deletes the selected runs, after asking for confirmation.

The list updates automatically after every new test.

**Why:** The task asks for easy retrieval and comparison of past results. The box plots also show if an ammeter
gives similar values from run to run (performance consistency, a bonus requirement).

## 10. Comparing the ammeter types

**What changed:** The History tab has a new **Ammeter comparison** table (under the chart, next to **Results**).
It compares the ammeter types over the selected runs (one run or several). After each test, the
**New test** tab also shows which ammeter was the most reliable in that run, and the full comparison is
printed in the terminal.

**An important limit first:** true **accuracy** (how close a reading is to the real current) can't be measured here.
That needs a known reference current, and the emulators just return random values.
So the program compares what *can* be measured, and says this clearly in the results.

| Column | Meaning |
|---|---|
| Rank | 1 = the most reliable ammeter |
| Success rate | How many of the requested measurements arrived (communication reliability) |
| CV (%) | Coefficient of variation = standard deviation / mean. How much the readings spread, compared to their size. Lower = steadier (more precise). It works even though the ammeters measure very different currents. |
| 95% CI of mean | 95% confidence interval of the mean, as +/- % of the mean. We are 95% sure the true average is inside this range. Narrower = more precise. |
| Run-to-run CV (%) | How much the average changes from one run to another (consistency). Needs at least 2 runs. |
| Timing | OK, or in how many runs the measurements were late |

**How the ranking works:**

1. The highest success rate wins, because an ammeter that loses measurements is less reliable.
2. If the success rate is the same, the lowest CV (steadiest readings) wins.
3. Ammeters with fewer than 10 readings are not ranked, because their statistics are not reliable enough.

**Notes the program adds under the table:**

- **Most reliable:** which ammeter won and why. If it won by success rate and another ammeter has steadier readings, it says so.
- **Too close to call:** if the top two have almost the same CV (less than 20% apart), their order may change from
  run to run, so the program suggests longer tests instead of naming a winner by chance.
- **Agreement:** if the ammeters' averages are very different. In these tests they differ by a factor of
  about 300-3,000, which shows that the emulators don't measure the same current (each returns independent random
  values). With real ammeters on the same circuit, this would be a red flag.

**What we found in our tests (original emulators):** Greenlee always has the highest CV (about 150-175% in short
tests, and over 700% with 500 readings), because its current is a random voltage divided by a random resistance,
which sometimes gives very large values. ENTES and CIRCUTOR have similar
CVs (about 45-65%), so their order changes between runs.

**Why:** This is the "Accuracy Assessment" bonus: compare the ammeter types, find relative accuracy and the most
reliable measurement method, and use statistics to measure precision.

**Statistics details:** The confidence interval uses Student's t distribution (correct for small samples),
with the critical values written in the code, so no extra library (like scipy) is needed.

## 11. Realistic emulator mode (optional)

**What changed:** The emulators can now run in a **realistic mode**. Turn it on with the
**Realistic (fixed device constants)** check box in the **Emulators** box of the New test tab.
The check box is locked while a test is running, so the mode can't change in the middle of a test.

It can also be turned on when the program starts (the check box is then already checked):

```sh
python main.py              # original emulators (default, unchanged behavior)
python main.py --realistic  # start with realistic emulators
```

In the original emulators, every measurement picks new random values for **everything**, including values that are
fixed in a real device. In realistic mode, those device constants are chosen randomly at the **first measurement**
and then stay the same until the program is closed. Only the measured quantity changes:

| Ammeter | Fixed in realistic mode (device constant) | Still random in every measurement |
|---|---|---|
| Greenlee | Resistance (the shunt resistor) | Voltage |
| ENTES | Calibration factor | Magnetic field |
| CIRCUTOR | Time step (the sampling rate) | The 10 voltages |

The fixed values are shown in the Emulators box after the first realistic test
(e.g. `Greenlee: resistance = 86.6875`), and printed in the terminal.
Turning realistic mode off and on again keeps the same values, like reconnecting the same device.
New values are chosen only when the program is started again.

**Why:** In a real ammeter, the shunt resistance and the calibration factor are set in the factory, and the sampling
rate is set by the device. Changing them in every measurement is like a meter whose calibration changes between
readings, and this was most of the noise in the original emulators.
All three ammeters are changed in the same way, so the ammeter comparison stays fair.

**Why it is optional:** The task says to use the existing ammeter emulation infrastructure. This is not a bug fix,
so the original behavior stays the default, and realistic mode is an extra option.

**Results:** Coefficient of variation (CV) over 500 readings of each ammeter:

| Ammeter | Original | Realistic |
|---|---|---|
| Greenlee | 738% | 45% |
| ENTES | 62% | 47% |
| CIRCUTOR | 48% | 14% |

In realistic mode, CIRCUTOR is clearly the steadiest, because it adds up 10 voltages, which averages out the noise.
In original mode, Greenlee's CV grows with the number of readings, because rare very small resistances give
very large currents.

**Saved with every run:** Each run saves its emulator mode, and in realistic mode also the fixed device constants
(in `run.json` under `setup`). The History tab shows the mode in the **Emulators** column, and the constants
when one run is selected. The History tab warns when the selected runs used different modes,
because their results are not directly comparable. Runs saved before this change are shown as "original".

**Changed files:** `Ammeters/base_ammeter.py` (the `realistic` option, the `device_constant()` method and the
`device_constants` property), `Greenlee_Ammeter.py`, `Entes_Ammeter.py` and `Circutor_Ammeter.py` (one line each:
the device constant uses `device_constant()`), `main.py` (the `Emulators` class that starts the emulators and
switches their mode, and the `--realistic` option), and `src/gui/measurement_app.py` (the check box).

## 12. Accuracy assessment tab

**What changed:** A third tab, **Accuracy assessment**, compares the ammeter types over test runs picked by hand.

**Picking runs (left side):**

- A list of all saved runs. Click a run to tick or untick it.
- **Show** filter: all runs, only original emulators, or only realistic emulators.
- **Select all**, **Clear**, and **Last [N] runs** (ticks the newest N runs in the list).
- The analysis updates as soon as runs are ticked or unticked.
- A warning appears if the ticked runs used different emulator modes, and a note if they used different settings.
- An **Hz** column shows each run's sampling frequency, so it's easy to see which frequencies were late.
- A **Timing** column shows if each run kept its timing (**OK**) or had late measurements (**Late**, in orange).

**What the tab shows (right side):**

1. **Verdict** at the top: the most reliable ammeter and why.
2. **A card for each ammeter**, ordered by rank: mean, median, standard deviation, min / max, CV with its 95% range,
   success rate, run-to-run CV, timing (in how many runs it was late) and the largest delay.
   The most reliable ammeter has a thick border and a star.
3. **Four charts:**

| Chart | Question it answers |
|---|---|
| 1. Precision: CV per ammeter | Which ammeter is the most precise? Bars are the CV (lower is better), the error bars are the 95% range of the CV. |
| 2. Spread relative to each ammeter's mean | How much do the readings spread? Each reading is divided by its ammeter's mean, so all ammeters fit on one scale, although their currents are very different. |
| 3. Consistency between runs | Does each ammeter give the same average in every run? Each run's average is shown as % of the ammeter's overall average (needs 2 or more runs). |
| 4. Agreement: range of the readings | Do the ammeters agree with each other? Min-max, mean and median on a log scale, so 0.03 A and 100 A fit on one chart. |

4. **Notes** under the charts: if the winner is significantly better, how well the ammeters agree, and why accuracy
   can't be measured.

**Zooming into the charts:** drag a box on a chart to zoom into that area, or scroll the mouse wheel to zoom in and
out around the mouse pointer. Double-click a chart to go back to its full view. Each chart zooms on its own.
This is needed because a few very large readings can squash a chart: in chart 2, Greenlee readings up to 120 times
its mean make the boxes of all three ammeters look flat, and zooming in shows them. The charts are images (see
"Windows blocked part of matplotlib" below), so matplotlib's own zoom toolbar can't be used. The zoom is built
in `chart_view.py` instead: the mouse position is converted to chart values with matplotlib's coordinate
transforms, so it works on the log scale of chart 4 too. Changing the selected runs redraws the charts at full view.

**New statistical technique: bootstrap range of the CV.** To check if the winner is really steadier, or won by chance:

- The readings are re-sampled (randomly picked again, with repeats) 1,000 times, and the CV is calculated each time.
- The middle 95% of these CVs is the "95% range" of the CV.
- If the winner's range and the runner-up's range don't overlap, the difference is **significant**.
  If they overlap, the order may be chance, and the tab suggests selecting more runs or running longer tests.
- It uses only Python's built-in `random` module, with a fixed seed, so the same runs always give the same result.

**Why:** This tab implements the "Accuracy Assessment" bonus of the task:

| Task point | How the tab answers it |
|---|---|
| Compare measurements across different ammeter types | Cards, charts and notes for all ammeters, over the same runs |
| Determine relative accuracy | Chart 4 and the "relative agreement" note. True accuracy needs a reference (see below). |
| Identify most reliable measurement method | The verdict, the rank on each card and the star |
| Use statistical techniques to quantify measurement precision | CV, 95% confidence interval of the mean, run-to-run CV, and the bootstrap range of the CV |

**About accuracy:** True accuracy (how close a reading is to the real current) needs a known reference: a calibrated
current source, or a calibrated reference meter on the same circuit. The emulators return independent random
values, so the tab compares reliability, precision, consistency and agreement, and says so clearly.

**Timing in the assessment:** If some of the ticked runs had late measurements, an orange note at the top says how
many, and which run had the largest delay. The late runs are still included, because their readings are valid,
but they were taken after their planned time, so the run didn't keep the sampling frequency. If all the late runs
were above 30 Hz, the note also suggests using 30 Hz or less. The note and the cards also say how many readings
were late, and the Timing column in the runs list shows the share of late readings, e.g. "Late 0.3%".
On the cards, "Timing", "Late readings" and "Max delay" are orange when an
ammeter was late. Before this change the tab didn't show timing at all, so a run with delays looked the same as
a run without them.

**Example result (3 realistic runs, 40 measurements each):** CIRCUTOR was the most reliable, with a CV of 14.9%
(95% range 13-17%), significantly steadier than ENTES (46.5%, range 41-52%) and Greenlee (46.7%, range 41-52%).

## 13. Automated tests

**What changed:** A new `tests/` folder with 19 automated tests, run with `python -m unittest -v`.
They check the sampling settings, the statistics and ranking, saving and loading runs, the communication
with an ammeter, and that a test continues after failed measurements. One test checks the Greenlee output fix
(`FIXES.md`, Fix 5): it was checked to fail with the original code and pass with the fix.

**Why:** The task is about software testing, so the framework itself should be tested too. The tests use only
Python's built-in `unittest`, a fake ammeter server and a temporary folder, so they don't need the emulators,
work while `main.py` is running, and never change `results/`.

The History tab was also fixed: its Timing columns were too narrow for the new text (for example
"Late 323/500 (64.6%)"), so the text was cut off. They are wider now.

## Files

| File | Status | What it does |
|---|---|---|
| `main.py` | Changed | Starts the three emulators and opens the window |
| `Ammeters/client.py` | Changed | Added `read_current_from_ammeter()`, which returns the measurement instead of only printing it, and stops waiting after 2 seconds |
| `src/testing/ammeters.py` | New | Describes each ammeter type and how to measure it |
| `src/testing/results.py` | New | Sampling settings, result format, statistics, the text report, and the run ID |
| `src/testing/analysis.py` | New | Compares the ammeter types: success rate, CV, confidence interval, bootstrap range of the CV, ranking and notes |
| `src/testing/result_store.py` | New | Saves test runs to the `results` folder, lists them, loads and deletes them |
| `src/testing/sampling.py` | New | Timing and data collection |
| `src/testing/test_framework.py` | Filled in (was empty) | The testing interface: `run_test()` and `run_tests()` |
| `src/gui/measurement_app.py` | New | The window and the "New test" tab: settings, live chart and results |
| `src/gui/history_tab.py` | New | The "History" tab: list, view, compare and delete saved runs |
| `src/gui/analysis_tab.py` | New | The "Accuracy assessment" tab: pick runs and compare the ammeter types |
| `src/gui/chart_view.py` | New | Shows charts in the window (shared by all tabs), gives each ammeter its own color, and zooms into the Accuracy assessment charts |
| `tests/` | New | 19 automated tests (see section 13) |
| `requirements.txt` | Changed | Lists only matplotlib, the one library the code needs (see "Installed libraries") |
| `README.md` | Rewritten | Installation, running, using the window, results, Python example, project structure and troubleshooting |

The emulator files were changed only for the CIRCUTOR command fix (see `FIXES.md`) and for the optional
realistic mode (see section 11). Without `--realistic`, the emulators behave exactly as before.

## Installed libraries

| Library | Version | Why |
|---|---|---|
| matplotlib | 3.11.2 | Draws the charts |

Installing matplotlib also installed the libraries it needs, including numpy 2.5.4 and pillow 13.0.0.
The window uses Tkinter, which comes with Python. Tested with Python 3.13 on Windows 11.

The code needs **matplotlib 3.5 or newer**, because the charts use `layout="constrained"`, which was added in 3.5.

Install command:

```sh
python -m pip install -r requirements.txt
```

### `requirements.txt` changed

**What changed:** `requirements.txt` now lists only `matplotlib>=3.5`. Before, it listed six libraries:

| Library | Before | Now | Why |
|---|---|---|---|
| matplotlib | `>=3.4.0` | `>=3.5` | The code needs 3.5 or newer (see above). With 3.4 the window would not open. |
| numpy | `>=1.21.0` | Removed | Not used by the code. It is still installed automatically, because matplotlib needs it. |
| scipy | `>=1.7.0` | Removed | Not used. The statistics are calculated with Python's built-in `statistics` module. |
| seaborn | `>=0.11.0` | Removed | Not used. The charts are drawn with matplotlib only. |
| pandas | `>=1.3.0` | Removed | Not used. The results are saved with Python's built-in `json` and `csv` modules. |
| pyyaml | `>=6.0` | Removed | Not used yet. It is needed only if the settings are read from `config.yaml` (see "Not done yet"). |

**Why:** The task asks to minimize external library dependencies. Installing five unused libraries makes the
installation slower and larger, and can cause version conflicts, without adding anything. Now `requirements.txt`
lists exactly what the code needs, so `python -m pip install -r requirements.txt` is the install command in the README too.

## Problems found and how they were solved

**1. Windows blocked part of matplotlib**
Windows Application Control (Smart App Control) blocked a matplotlib file (`_tkagg`) that is normally used to show
charts inside a Tkinter window. Instead, the chart is drawn in memory as a PNG image and shown in the window.
It looks the same, updates the same, and works on every operating system.

**2. The chart made the timing less accurate**
Drawing the chart made some measurements 6-19 ms late, because Python runs only one thread at a time.
Two changes brought the delay back to about 1-2 ms:

- The chart is redrawn every 250 ms, and only when new measurements arrived.
- Python switches between threads more often (`sys.setswitchinterval`), so the measurement threads don't wait for the chart.

**3. The ammeters have a speed limit**
Each measurement opens a new network connection, and the emulator prints every measurement to the terminal.
One measurement takes a few milliseconds, so the emulators can't keep up with very high frequencies
(in a test at 300 Hz, measurements were up to about 1 second late). The program doesn't lose data in this case.
It shows a warning before the test (above 30 Hz) and shows how many measurements were late.

The warning limit was first 50 Hz. An earlier set of 9 test runs (since replaced by the current sample runs)
showed that this was too high:

| Frequency | Late readings |
|---|---|
| 20 Hz, 30 Hz | 0 |
| 33 Hz | 1 of 300 (0.3%) |
| 50 Hz | 82 of 600 (13.7%) |
| 58-60 Hz | 17-27% |
| 87.5-125 Hz | 49-80% |

So the limit was lowered to 30 Hz. The current sample runs (see [SAMPLE_RESULTS.md](SAMPLE_RESULTS.md)) show the
same trend, but also that the limit isn't exact:

| Frequency | Late readings (current sample runs) |
|---|---|
| 15 Hz, 20 Hz | 0 |
| 25 Hz | 1 of 300 (0.3%) and 3 of 300 (1.0%) |
| 28.6 Hz | 57 of 600 (9.5%) |
| 50 Hz | 38 of 900 (4.2%) and 68 of 300 (22.7%) |

The limit depends on how busy the computer is: in an earlier test, 50 Hz had delays of only 1-2 ms, a 60 Hz test
had no late readings, and in the sample runs a 28.6 Hz run had late readings. That is why it is a warning, not a
block, and why every run reports how many of its readings were late.

Before, a run was marked only **Late** or **OK**, so one late reading (like the 25 Hz sample run) looked the same as
a run where many readings were late. Now the result shows how many readings were late, in the results table, the
text report and the Accuracy assessment tab. The earlier 9 runs were saved before this change, so their number of
late readings was calculated once from their `readings.csv` (actual time vs. planned time of each reading). The
current sample runs were all saved after this change. Runs saved without this number show only **Late**.

## Not done yet

- **Settings from `config.yaml`:** The settings are entered in the window. Reading them from `config.yaml`
  (a bonus requirement) needs the `pyyaml` library, which is not installed yet.
- **Terminal output:** The emulators still print every measurement to the terminal. This doesn't affect the window.
