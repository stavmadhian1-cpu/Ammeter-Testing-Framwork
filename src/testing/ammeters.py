from dataclasses import dataclass

from Ammeters.client import read_current_from_ammeter


@dataclass(frozen=True)
class Ammeter:
    """
    One ammeter type, as the test framework sees it. Every type is measured the same way through `measure()`,
    only the port and the command are different.
    """
    type: str      # Key used to select the ammeter, e.g. "greenlee"
    name: str      # Name shown in reports
    port: int
    command: bytes
    method: str    # Measurement method, from README.md

    def measure(self, timeout: float = 2.0) -> float:
        """
        Takes one measurement and returns the current in A.
        Raises OSError if the ammeter can't be reached in time, or ValueError if it sends no valid value.
        """
        return read_current_from_ammeter(self.port, self.command, timeout)

    def to_dict(self) -> dict:
        return {"type": self.type, "name": self.name, "port": self.port, "command": self.command.decode("utf-8"),
                "method": self.method}

    @classmethod
    def from_dict(cls, data: dict) -> "Ammeter":
        return cls(data["type"], data["name"], data["port"], data["command"].encode("utf-8"), data["method"])


# All supported ammeter types, with the ports and commands listed in README.md
AMMETERS = {
    ammeter.type: ammeter for ammeter in (
        Ammeter("greenlee", "Greenlee", 5000, b'MEASURE_GREENLEE -get_measurement', "Ohm's law: I = V / R"),
        Ammeter("entes", "ENTES", 5001, b'MEASURE_ENTES -get_data', "Hall effect: I = B * K"),
        Ammeter("circutor", "CIRCUTOR", 5002, b'MEASURE_CIRCUTOR -get_measurement',
                "Rogowski coil integration: I = integral of V dt"),
    )
}


def get_ammeter(ammeter_type: str) -> Ammeter:
    """
    Returns the ammeter of the given type (not case sensitive), or raises ValueError if the type is unknown.
    """
    try:
        return AMMETERS[ammeter_type.strip().lower()]
    except KeyError:
        raise ValueError(f"Unknown ammeter type '{ammeter_type}'. Available types: {', '.join(AMMETERS)}")
