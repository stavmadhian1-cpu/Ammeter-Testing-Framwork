# Code Fixes

This file lists the bugs found in the provided code and how they were fixed.
Fixes 1-4 made `main.py` run and return current measurements from the ammeter emulators.
Fixes 5-7 fixed errors found later in the provided files.

> **Note about `main.py`:** Fixes 1-4 describe the original `main.py`, as it was when it was fixed. Later, `main.py`
> was rewritten to open the measurement window (see [CHANGES.md](CHANGES.md), section 1), so the lines shown in
> Fixes 1-4 are no longer in `main.py`. The fixes are still in use:
>
> | Fix | Where it is now |
> |---|---|
> | Fixes 1-2: send the full command of each ammeter | `src/testing/ammeters.py` (lines 37-40): every measurement sends the full command |
> | Fix 3: ports 5000-5002 | `main.py` (lines 17-19) starts the emulators on these ports, and `src/testing/ammeters.py` (lines 37-40) sends the requests to them |
> | Fix 4: CIRCUTOR command without `-current` | `Ammeters/Circutor_Ammeter.py` (line 9) and `src/testing/ammeters.py` (line 39) |
>
> The single-request function `request_current_from_ammeter()` is still in `Ammeters/client.py`. The framework uses
> `read_current_from_ammeter()`, which returns the value instead of printing it.

## Fix 1: Uncomment the measurement requests in `main.py`

**File:** `main.py` (lines 33-35)

**Problem:** The three calls to `request_current_from_ammeter` were commented out. The emulators started, but `main.py` never sent them a request, so no measurements were shown.

**Before:**
```python
    # request_current_from_ammeter(5001, b'MEASURE_GREENLEE')  # Request from Greenlee Ammeter
    # request_current_from_ammeter(5002, b'MEASURE_ENTES')  # Request from ENTES Ammeter
    # request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR')  # Request from CIRCUTOR Ammeter
```

**After:**
```python
    request_current_from_ammeter(5001, b'MEASURE_GREENLEE')  # Request from Greenlee Ammeter
    request_current_from_ammeter(5002, b'MEASURE_ENTES')  # Request from ENTES Ammeter
    request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR')  # Request from CIRCUTOR Ammeter
```

**Fix:** Removed the `#` at the start of lines 33-35 so the client now sends a request to each emulator.

**Result:** The emulators received the requests (`Connected by ...`), but each request still printed `No data received.` This led to Fix 2.

## Fix 2: Send the full command to each ammeter in `main.py`

**File:** `main.py` (lines 33-35)

**Problem:** Each emulator answers only when the message it receives exactly matches its command (`base_ammeter.py`, lines 27-30). `main.py` sent only the first part of each command, so the emulators sent nothing back and the client printed `No data received.`

| Ammeter | Port | Command sent before | Command the emulator expects |
|---|---|---|---|
| Greenlee | 5001 | `MEASURE_GREENLEE` | `MEASURE_GREENLEE -get_measurement` (`Greenlee_Ammeter.py`, line 9) |
| ENTES | 5002 | `MEASURE_ENTES` | `MEASURE_ENTES -get_data` (`Entes_Ammeter.py`, line 9) |
| CIRCUTOR | 5003 | `MEASURE_CIRCUTOR` | `MEASURE_CIRCUTOR -get_measurement -current` (`Circutor_Ammeter.py`, line 9) |

**Before:**
```python
    request_current_from_ammeter(5001, b'MEASURE_GREENLEE')  # Request from Greenlee Ammeter
    request_current_from_ammeter(5002, b'MEASURE_ENTES')  # Request from ENTES Ammeter
    request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR')  # Request from CIRCUTOR Ammeter
```

**After:**
```python
    request_current_from_ammeter(5001, b'MEASURE_GREENLEE -get_measurement')  # Request from Greenlee Ammeter
    request_current_from_ammeter(5002, b'MEASURE_ENTES -get_data')  # Request from ENTES Ammeter
    request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR -get_measurement -current')  # Request from CIRCUTOR Ammeter
```

**Fix:** Changed each command to match the exact command defined in the ammeter's emulator file.

**Result:** Every ammeter now returns a measurement. The values are random, so they change on every run. Example output:
```
Received current measurement from port 5001: 0.1831785250439037 A
Received current measurement from port 5002: 27.238171165837493 A
Received current measurement from port 5003: 0.042958726387896246 A
```

**Note:** `README.md` gives the CIRCUTOR command without `-current` at the end. The commands above come from the emulator source files, not from the README. This is fixed in Fix 4.

## Fix 3: Use the ports listed in `README.md`

**File:** `main.py` (lines 11, 15, 19 and 33-35)

**Problem:** The ports in `main.py` (5001-5003) did not match the ports in `README.md` (5000-5002). Each ammeter was one port higher than documented.

| Ammeter | Port before | Port after (README) |
|---|---|---|
| Greenlee | 5001 | 5000 |
| ENTES | 5002 | 5001 |
| CIRCUTOR | 5003 | 5002 |

**Before:**
```python
def run_greenlee_emulator():
    greenlee = GreenleeAmmeter(5001)
    greenlee.start_server()

def run_entes_emulator():
    entes = EntesAmmeter(5002)
    entes.start_server()

def run_circutor_emulator():
    circutor = CircutorAmmeter(5003)
    circutor.start_server()
...
    request_current_from_ammeter(5001, b'MEASURE_GREENLEE -get_measurement')  # Request from Greenlee Ammeter
    request_current_from_ammeter(5002, b'MEASURE_ENTES -get_data')  # Request from ENTES Ammeter
    request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR -get_measurement -current')  # Request from CIRCUTOR Ammeter
```

**After:**
```python
def run_greenlee_emulator():
    greenlee = GreenleeAmmeter(5000)
    greenlee.start_server()

def run_entes_emulator():
    entes = EntesAmmeter(5001)
    entes.start_server()

def run_circutor_emulator():
    circutor = CircutorAmmeter(5002)
    circutor.start_server()
...
    request_current_from_ammeter(5000, b'MEASURE_GREENLEE -get_measurement')  # Request from Greenlee Ammeter
    request_current_from_ammeter(5001, b'MEASURE_ENTES -get_data')  # Request from ENTES Ammeter
    request_current_from_ammeter(5002, b'MEASURE_CIRCUTOR -get_measurement -current')  # Request from CIRCUTOR Ammeter
```

**Fix:** Changed the port of each emulator and its matching request to the port in `README.md`. The server port and the request port must be the same for each ammeter, so both were changed together.

**Result:** Every ammeter returns a measurement on its README port. Example output:
```
Received current measurement from port 5000: 0.1068352382047387 A
Received current measurement from port 5001: 19.231874808194597 A
Received current measurement from port 5002: 0.011989081360132417 A
```

## Fix 4: Use the CIRCUTOR command listed in `README.md`

**Files:** `Ammeters/Circutor_Ammeter.py` (line 9) and `main.py` (line 35)

**Problem:** The CIRCUTOR emulator expected `MEASURE_CIRCUTOR -get_measurement -current`, but `README.md` documents the command as `MEASURE_CIRCUTOR -get_measurement`. The emulator did not match its documentation.

**Before:**

`Ammeters/Circutor_Ammeter.py`, line 9:
```python
        return b'MEASURE_CIRCUTOR -get_measurement -current'
```

`main.py`, line 35:
```python
    request_current_from_ammeter(5002, b'MEASURE_CIRCUTOR -get_measurement -current')  # Request from CIRCUTOR Ammeter
```

**After:**

`Ammeters/Circutor_Ammeter.py`, line 9:
```python
        return b'MEASURE_CIRCUTOR -get_measurement'
```

`main.py`, line 35:
```python
    request_current_from_ammeter(5002, b'MEASURE_CIRCUTOR -get_measurement')  # Request from CIRCUTOR Ammeter
```

**Fix:** Removed `-current` from the command in both files. The emulator answers only when the request exactly matches its command, so both files must use the same command. Changing only the emulator made CIRCUTOR print `No data received.` again.

**Result:** All three ammeters return a measurement, and the ports and commands now match `README.md`. Example output:
```
Received current measurement from port 5000: 0.021325296652540886 A
Received current measurement from port 5001: 51.99958309625946 A
Received current measurement from port 5002: 0.05045360068818418 A
```

## Fix 5: The Greenlee emulator crashed when its output isn't UTF-8

**File:** `Ammeters/Greenlee_Ammeter.py` (line 15)

**Problem:** The Greenlee emulator prints every measurement with the symbol `Ω`. When the output can't show this
symbol, `print()` raises a `UnicodeEncodeError`. This happens, for example, on Windows when the output is redirected
to a file or a pipe (the default encoding there is cp1252, which has no `Ω`). The error is raised inside the
emulator's server thread, so the **whole Greenlee server stopped**: the first request got no data, and every later
request timed out until the program was restarted. ENTES and CIRCUTOR kept working, so it looked like a broken
ammeter, not a printing problem.

How it was found: running the emulator with its output redirected (`PYTHONIOENCODING=cp1252`):
```
request 1: FAILED ValueError: No data received from port 5100
UnicodeEncodeError: 'charmap' codec can't encode character 'Ω' in position 77: character maps to <undefined>
request 2: FAILED TimeoutError: timed out
request 3: FAILED TimeoutError: timed out
```

**Before:**
```python
        print(f"Greenlee Ammeter - Voltage: {voltage}V, Resistance: {resistance}Ω, Current: {current}A")
```

**After:**
```python
        print(f"Greenlee Ammeter - Voltage: {voltage}V, Resistance: {resistance} Ohm, Current: {current}A")
```

**Fix:** Wrote the unit as `Ohm` instead of the symbol. Plain ASCII text can be printed with any encoding,
on any operating system. The measurement itself didn't change. No other print in the project uses a non-ASCII symbol.

**Result:** With the same redirected output, all requests return a measurement and the server keeps running:
```
request 1: 0.7949125086909744
request 2: 0.20572731574513575
request 3: 0.3207795719632256
```

## Fix 6: `examples/run_tests.py` didn't run

**File:** `examples/run_tests.py`

**Problem:** The example had three errors:

1. It called `framework.run_test()` without an ammeter type or settings, so it raised a `TypeError`.
2. It printed only a title for each ammeter, never the results.
3. Run as `python examples/run_tests.py`, Python couldn't find the `src` package (`ModuleNotFoundError`),
   because the project folder isn't on Python's path when a script in a subfolder is run.

Its comments were in Hebrew, unlike the rest of the code.

**Before:**
```python
from src.testing.test_framework import AmmeterTestFramework

def main():
    framework = AmmeterTestFramework()
    ammeter_types = ["greenlee", "entes", "circutor"]
    results = {}
    for ammeter_type in ammeter_types:
        print(f"Testing {ammeter_type} ammeter...")
        results[ammeter_type] = framework.run_test()
    for ammeter_type, result in results.items():
        print(f"\nResults for {ammeter_type}:")
```

**After (main part):**
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # find the project's packages
...
settings = SamplingSettings.from_values(count=args.count, frequency=args.frequency)
run = framework.run_tests(framework.available_types(), settings)
print(run.to_text() + "\n\n" + comparison_text([run]))
```

**Fix:** Rewrote the example to use the framework's real API:

- It tests all three ammeters at the same time with `run_tests()` and prints the full report and the ammeter comparison.
- It uses the emulators of a running `main.py`, or starts its own if they aren't running.
- Options: `--count`, `--frequency` and `--save` (saves the run in `results/`, like a run from the window).
  Wrong settings give a clear message instead of a traceback.
- Comments in English.

**Result:**
```
python examples/run_tests.py --count 20 --frequency 20
Testing Greenlee, ENTES, CIRCUTOR: 20 measurements, 1 s, 20 Hz
...
Ammeter   Collected  Errors  Mean (A)   Median (A)  Std dev (A)  Min (A)     Max (A)   Max delay (ms)  Timing
Greenlee  20 / 20    0       0.460079   0.141589    0.846769     0.0149402   3.68557   2.18            OK
ENTES     20 / 20    0       69.7589    65.7225     34.2633      17.8096     143.633   1.96            OK
CIRCUTOR  20 / 20    0       0.0290447  0.026493    0.017531     0.00582464  0.061384  2.29            OK
```

## Fix 7: `src/utils/logger.py` never wrote anything

**File:** `src/utils/logger.py`, now used by `src/testing/test_framework.py`

**Problem:** `TestLogger` chose a log file name, but never attached a handler to the logger, so no message was
ever written. It also had no log level (so `info()` and `debug()` were ignored), and nothing in the project used it.
Other issues:

- The log folder `results/logs` was relative to the current folder, so logs went to a different place depending on
  where the program was started.
- Two loggers for the same test name would share one Python logger, so every message would be written twice.
- The file was never closed (on Windows an open file can't be deleted or moved).
- Its comments were in Hebrew.

**Before:**
```python
        logger = logging.getLogger(f"test_{self._test_name}")


        return logger
```

**After:**
```python
        logger = logging.getLogger(f"test_{self._test_name}_{next(_instances)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Only to the file, not to the terminal
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
        logger.addHandler(handler)
        return logger
```

**Fix:**

- Added a file handler (UTF-8), a log level and a line format with the time and level.
- The log folder is `results/logs` in the project folder, wherever the program is started from.
- Each logger gets its own name, and a new `close()` method releases the file.
- The existing methods (`info`, `error`, `debug`, `warning`) are kept, so the original design stays the same.
- **The logger is now used:** every test (from the window, the example or Python) writes its own log file,
  `results/logs/<date>_<time>_<ammeters>.log`. It logs the start and settings, one line per ammeter
  (collected, errors, mean, max delay, timing), every failed measurement as `ERROR`, late timing as `WARNING`,
  and a test that failed or was stopped. `AmmeterTestFramework(log_dir=None)` turns logging off.

**Result:** Example log of a test with an ammeter that doesn't answer:
```
2026-11-04 10:47:46,520  INFO     Run ID 20261104_104740_983a: Test finished in 6.022 s.   Settings: 3 measurements, 0.3 s, 10 Hz
2026-11-04 10:47:46,520  INFO     Dead: collected 0/3, 3 errors, mean -, max delay 3806.39 ms, timing Late 2/3 (66.7%)
2026-11-04 10:47:46,520  ERROR    Dead - Measurement 1: timed out
2026-11-04 10:47:46,520  ERROR    Dead - Measurement 2: timed out
2026-11-04 10:47:46,520  ERROR    Dead - Measurement 3: timed out
2026-11-04 10:47:46,521  WARNING  Dead: late measurements, Late 2/3 (66.7%)
2026-11-04 10:47:46,521  INFO     Test finished.
```
