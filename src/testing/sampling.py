import threading
import time
from datetime import datetime

from src.testing.ammeters import Ammeter
from src.testing.results import AmmeterResult, SamplingSettings, TestRun

# Above this frequency the emulators may not answer fast enough and measurements will be late.
# Measured on Windows 11: at 15-20 Hz no reading was late, at 50 Hz 4-23% were late. The real limit depends on
# how busy the computer is, so this is a warning, not a limit (see SAMPLE_RESULTS.md).
RECOMMENDED_MAX_FREQUENCY_HZ = 30


def _sleep_until(target: float, stop_event: threading.Event):
    """
    Sleeps until the `perf_counter` time `target`, in short steps so a stop request is noticed quickly.
    """
    while not stop_event.is_set():
        remaining = target - time.perf_counter()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.05))


def sample_ammeter(ammeter: Ammeter, settings: SamplingSettings, start_time: float, stop_event: threading.Event,
                   on_reading=None) -> AmmeterResult:
    """
    Takes `settings.count` measurements from one ammeter, one every `settings.interval` seconds,
    starting at the `perf_counter` time `start_time`.
    Each measurement is scheduled from the start time (not from the previous measurement),
    so small delays don't add up over the test.
    `on_reading(ammeter_type, seconds, current)` is called after every successful measurement.
    """
    result = AmmeterResult(ammeter, settings, late_count=0)
    for i in range(settings.count):
        scheduled = start_time + i * settings.interval
        _sleep_until(scheduled, stop_event)
        if stop_event.is_set():
            break
        actual = time.perf_counter()
        result.max_delay = max(result.max_delay, actual - scheduled)
        if actual - scheduled > settings.interval:
            result.late_count += 1
        try:
            current = ammeter.measure()
        except (OSError, ValueError) as error:
            result.errors.append(f"Measurement {i + 1}: {error}")
            continue
        result.readings.append((actual - start_time, current))
        if on_reading:
            on_reading(ammeter.type, actual - start_time, current)
    return result


def run_sampling(ammeters: list, settings: SamplingSettings, stop_event: threading.Event = None,
                 on_reading=None) -> TestRun:
    """
    Samples the given ammeters at the same time, each in its own thread, and returns the results.
    Returns early if `stop_event` is set.
    """
    stop_event = stop_event or threading.Event()
    run = TestRun(settings, datetime.now())
    # All ammeters share the same start time, so their measurements are taken at the same moments
    start_time = time.perf_counter() + 0.1

    def sample(ammeter: Ammeter):
        run.results[ammeter.type] = sample_ammeter(ammeter, settings, start_time, stop_event, on_reading)

    threads = [threading.Thread(target=sample, args=(ammeter,)) for ammeter in ammeters]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # The test lasts the full duration: wait until the last measurement interval has ended
    _sleep_until(start_time + settings.duration, stop_event)

    run.total_time = time.perf_counter() - start_time
    run.stopped = stop_event.is_set()
    # Keep the results in the order the ammeters were given, not the order the threads finished
    run.results = {ammeter.type: run.results[ammeter.type] for ammeter in ammeters}
    return run
