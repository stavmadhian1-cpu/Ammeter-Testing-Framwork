from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.utils.Utils import generate_random_float


class GreenleeAmmeter(AmmeterEmulatorBase):
    @property
    def get_current_command(self) -> bytes:
        # Define the command to get the current from Greenlee
        return b'MEASURE_GREENLEE -get_measurement'

    def measure_current(self) -> float:
        voltage = generate_random_float(1.0, 10.0)  # Random voltage (1V - 10V)
        resistance = self.device_constant("resistance", 0.1, 100.0)  # Resistance (0.1Ω - 100Ω)
        current = voltage / resistance
        # "Ohm" instead of the symbol: printing it crashed the server when the output isn't UTF-8 (see FIXES.md, Fix 5)
        print(f"Greenlee Ammeter - Voltage: {voltage}V, Resistance: {resistance} Ohm, Current: {current}A")
        return current
