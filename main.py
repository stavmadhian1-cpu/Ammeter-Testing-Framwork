import argparse
import threading

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.gui.measurement_app import MeasurementApp


class Emulators:
    """
    The three ammeter emulators, each running in its own thread. The window uses this to switch realistic mode.
    """

    def __init__(self, realistic: bool = False):
        self.emulators = {
            "greenlee": GreenleeAmmeter(5000, realistic),
            "entes": EntesAmmeter(5001, realistic),
            "circutor": CircutorAmmeter(5002, realistic),
        }

    def start(self):
        for emulator in self.emulators.values():
            threading.Thread(target=emulator.start_server, daemon=True).start()

    def set_realistic(self, realistic: bool):
        # Device constants already chosen are kept, so turning realistic mode on again gives the same "device"
        for emulator in self.emulators.values():
            emulator.realistic = realistic

    def device_constants(self) -> dict:
        """
        The device constants chosen so far, per ammeter type, e.g. {"greenlee": {"resistance": 15.26}}.
        """
        return {ammeter_type: emulator.device_constants for ammeter_type, emulator in self.emulators.items()
                if emulator.device_constants}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ammeter emulators and measurement window")
    parser.add_argument("--realistic", action="store_true",
                        help="start with realistic emulators (can also be switched in the window): device constants "
                             "(Greenlee resistance, ENTES calibration factor, CIRCUTOR time step) are chosen once "
                             "and stay the same until the program closes")
    args = parser.parse_args()

    # Start each ammeter in a separate thread
    emulators = Emulators(args.realistic)
    emulators.start()

    # Open the measurement window. The emulators are ready long before the user can click "Start measurement".
    # If you have problem restarting the servers between runs, wait a few seconds before running again.
    MeasurementApp(realistic=args.realistic, set_realistic=emulators.set_realistic,
                   device_constants=emulators.device_constants).run()
