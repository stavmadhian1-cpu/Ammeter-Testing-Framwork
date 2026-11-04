# Sample Test Results

This file describes the sample test results included with the project (deliverable 3): where they are,
what each run shows, and what the comparison of the ammeters found.

## Where the results are

All sample results are in the [`results/`](results/) folder:

```
results/
├── index.csv                       List of all 8 runs (one line per run)
├── runs/<run ID>/                  One folder per run
│   ├── report.txt                  The text report: start here, it opens in any text editor
│   ├── run.json                    Metadata, settings, statistics, timing and errors
│   ├── readings.csv                Every measurement (opens in Excel)
│   └── chart.png                   The chart of the readings
└── logs/<date>_<time>_<ammeters>.log    The log file of each test
```

To see them in the program, run `python main.py` and open the **History** or **Accuracy assessment** tab.

## The 8 sample runs

All runs measured the three ammeters (Greenlee, ENTES, CIRCUTOR) at the same time. All finished, with 100% of
the measurements received and no errors.

| Run ID (folder) | Emulators | Settings | Timing | What it shows |
|---|---|---|---|---|
| [`20261104_122331_1675`](results/runs/20261104_122331_1675/report.txt) | Original | 100 meas., 4 s, 25 Hz | 1 of 300 readings late (0.3%) | A single late reading is reported, but doesn't spoil the run |
| [`20261104_122350_3fea`](results/runs/20261104_122350_3fea/report.txt) | Original | 200 meas., 7 s, 28.6 Hz | 57 of 600 late (9.5%) | Delays can happen even below 30 Hz when the computer is busy |
| [`20261104_122420_7217`](results/runs/20261104_122420_7217/report.txt) | Original | 100 meas., 6.7 s, 15 Hz | OK | A clean run in original mode |
| [`20261104_122435_d10a`](results/runs/20261104_122435_d10a/report.txt) | Original | 100 meas., 2 s, 50 Hz | 68 of 300 late (22.7%) | **Timing check example:** the emulators can't keep up at 50 Hz |
| [`20261104_122503_21b3`](results/runs/20261104_122503_21b3/report.txt) | Realistic | 50 meas., 3.3 s, 15 Hz | OK | A clean run in realistic mode |
| [`20261104_122522_4a6d`](results/runs/20261104_122522_4a6d/report.txt) | Realistic | 80 meas., 4 s, 20 Hz | OK | A clean run in realistic mode |
| [`20261104_122536_25b7`](results/runs/20261104_122536_25b7/report.txt) | Realistic | 100 meas., 4 s, 25 Hz | 3 of 300 late (1.0%) | A few late readings |
| [`20261104_122549_c65e`](results/runs/20261104_122549_c65e/report.txt) | Realistic | 300 meas., 6 s, 50 Hz | 38 of 900 late (4.2%) | Late readings at 50 Hz in realistic mode too |

The 4 realistic runs were made in the same session, so they share the same device constants (saved in each
`run.json`): Greenlee resistance 48.2 Ω, ENTES calibration factor 1540, CIRCUTOR time step 0.00485 s.

## Comparison of the ammeters

These are the results of the **Accuracy assessment** tab, with all the runs of each emulator mode selected.

### Original emulators (4 runs, 500 readings per ammeter)

| Rank | Ammeter | Mean (A) | Median (A) | Std dev (A) | Min - Max (A) | CV (95% range) | Run-to-run CV |
|---|---|---|---|---|---|---|---|
| 1 | CIRCUTOR | 0.0304 | 0.0304 | 0.0146 | 0.0050 - 0.071 | 47.8% (45.1-50.6%) | 2.7% |
| 2 | ENTES | 66.28 | 57.14 | 41.17 | 5.69 - 193.6 | 62.1% (58.6-65.4%) | 5.5% |
| 3 | Greenlee | 0.515 | 0.113 | 3.07 | 0.012 - 61.6 | 595.9% (261-717%) | 86.3% |

### Realistic emulators (4 runs, 530 readings per ammeter)

| Rank | Ammeter | Mean (A) | Median (A) | Std dev (A) | Min - Max (A) | CV (95% range) | Run-to-run CV |
|---|---|---|---|---|---|---|---|
| 1 | CIRCUTOR | 0.0266 | 0.0266 | 0.0039 | 0.014 - 0.037 | 14.7% (13.8-15.6%) | 2.2% |
| 2 | ENTES | 84.97 | 85.22 | 38.81 | 15.85 - 153.4 | 45.7% (43.1-48.1%) | 5.7% |
| 3 | Greenlee | 0.114 | 0.117 | 0.054 | 0.021 - 0.207 | 47.3% (44.5-49.8%) | 5.4% |

All ammeters had a 100% success rate in both modes.

### What the results show

- **CIRCUTOR is the most reliable ammeter in both modes**, and the difference is **significant**: its 95% range of
  the CV doesn't overlap with the runner-up's (original: 45.1-50.6% vs 58.6-65.4%; realistic: 13.8-15.6% vs
  43.1-48.1%).
- **Greenlee is very unstable with the original emulators** (CV 596%, readings up to 61.6 A while the median is
  0.11 A). The original emulator picks a new random resistance for every reading, and a very small resistance
  gives a huge current. With realistic emulators (fixed resistance) its CV drops to 47% and its mean and median agree.
- **Consistency between runs:** CIRCUTOR's average changes by only 2-3% from run to run, ENTES and realistic
  Greenlee by about 5-6%, original Greenlee by 86%.
- **Relative accuracy:** the ammeters don't agree with each other. ENTES reads about 2,000 times more than CIRCUTOR,
  because each emulator returns independent random values. True accuracy can't be measured without a calibrated
  reference current, so the ranking is based on reliability and precision.
- **Timing:** delays grow with the frequency. Up to 20 Hz all runs were on time, at 25-28.6 Hz a few runs had late
  readings, and at 50 Hz 4-23% of the readings were late. The program warns above 30 Hz.

## Example: text report

From [`20261104_122435_d10a/report.txt`](results/runs/20261104_122435_d10a/report.txt), the 50 Hz run with late readings:

```
Test run 20261104_122435_d10a, started 2026-11-04 12:24:35, original emulators
Test finished in 2.000 s.   Settings: 100 measurements, 2 s, 50 Hz

Ammeter   Collected  Errors  Mean (A)   Median (A)  Std dev (A)  Min (A)     Max (A)    Max delay (ms)  Timing
--------  ---------  ------  ---------  ----------  -----------  ----------  ---------  --------------  -------------------
Greenlee  100 / 100  0       0.23982    0.110917    0.379489     0.0189822   2.33425    122.12          Late 24/100 (24.0%)
ENTES     100 / 100  0       69.0427    59.2118     42.8591      5.69108     187.726    121.20          Late 22/100 (22.0%)
CIRCUTOR  100 / 100  0       0.0313281  0.0341078   0.0146628    0.00545342  0.0657578  141.63          Late 22/100 (22.0%)
```

## Example: log file

From [`results/logs/20261104_122435_greenlee_entes_circutor.log`](results/logs/20261104_122435_greenlee_entes_circutor.log):

```
2026-11-04 12:24:35,956  INFO     Test started: Greenlee, ENTES, CIRCUTOR, 100 measurements, 2 s, 50 Hz, setup {'emulator_mode': 'original'}
2026-11-04 12:24:38,057  INFO     Run ID 20261104_122435_d10a: Test finished in 2.000 s.   Settings: 100 measurements, 2 s, 50 Hz
2026-11-04 12:24:38,058  INFO     Greenlee: collected 100/100, 0 errors, mean 0.23982 A, max delay 122.12 ms, timing Late 24/100 (24.0%)
2026-11-04 12:24:38,058  WARNING  Greenlee: late measurements, Late 24/100 (24.0%)
...
2026-11-04 12:24:38,080  INFO     Test finished.
```
