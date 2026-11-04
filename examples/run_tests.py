"""
Example: tests all ammeter types from Python, without the window, and prints the report.

Run from the project folder:
    python examples/run_tests.py
    python examples/run_tests.py --count 100 --frequency 20 --save

Uses the emulators of a running main.py, or starts its own if they aren't running.
"""
import argparse
import socket
import sys
import time
from pathlib import Path

# Lets the example find the project's packages when it is run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import Emulators
from src.testing.ammeters import AMMETERS
from src.testing.analysis import comparison_text
from src.testing.result_store import ResultStore
from src.testing.results import SamplingSettings
from src.testing.test_framework import AmmeterTestFramework


def emulator_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("localhost", port)) == 0


def main():
    parser = argparse.ArgumentParser(description="Test all ammeter types and print the report")
    parser.add_argument("--count", type=int, default=50, help="number of measurements per ammeter (default 50)")
    parser.add_argument("--frequency", type=float, default=10, help="sampling frequency in Hz (default 10)")
    parser.add_argument("--save", action="store_true", help="save the run in results/, like a run from the window")
    args = parser.parse_args()

    # Use the running emulators, or start them
    running = [emulator_running(ammeter.port) for ammeter in AMMETERS.values()]
    if not any(running):
        print("Starting the ammeter emulators...")
        Emulators().start()
        time.sleep(0.5)  # Give the emulators a moment to start listening
    elif not all(running):
        sys.exit("Some emulator ports are in use, but not all. Close the other program and try again.")

    try:
        settings = SamplingSettings.from_values(count=args.count, frequency=args.frequency)
    except ValueError as error:
        sys.exit(f"Wrong settings: {error}")

    framework = AmmeterTestFramework()
    print(f"Testing {', '.join(ammeter.name for ammeter in AMMETERS.values())}: {settings.describe()}")
    run = framework.run_tests(framework.available_types(), settings)

    print("\n" + run.to_text() + "\n\n" + comparison_text([run]))
    if args.save:
        print(f"\nSaved to: {ResultStore().save(run)}")


if __name__ == "__main__":
    main()
