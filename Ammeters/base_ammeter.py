import socket
import time
import random
from abc import ABC, abstractmethod

NotImplementedErrorMsg = "Subclasses must implement this property."

class AmmeterEmulatorBase(ABC):
    def __init__(self, port: int, realistic: bool = False):
        """
        realistic: if True, the device constants (like a shunt resistance or a calibration factor) are chosen randomly
        at the first measurement and stay the same while the emulator runs, like in a real device.
        If False (the default), they are random in every measurement, as in the original emulators.
        """
        self.port = port
        self.realistic = realistic
        self._device_constants = {}
        random.seed(time.time())  # Seed the random number generator for each instance

    @property
    def device_constants(self) -> dict:
        """
        The device constants chosen so far in realistic mode, e.g. {"resistance": 15.26}.
        """
        return dict(self._device_constants)

    def device_constant(self, name: str, min_value: float, max_value: float) -> float:
        """
        Returns the value of a device constant: a new random value every time,
        or in realistic mode the same random value for the whole session.
        """
        if not self.realistic:
            return random.uniform(min_value, max_value)
        if name not in self._device_constants:
            self._device_constants[name] = random.uniform(min_value, max_value)
            print(f"{self.__class__.__name__} (realistic mode) - fixed {name} for this session: "
                  f"{self._device_constants[name]}")
        return self._device_constants[name]

    def start_server(self):
        """
        Starts the server to listen for client requests.
        The server will run indefinitely, handling one client request at a time.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', self.port))
            s.listen()
            print(f"{self.__class__.__name__} is running on port {self.port}")
            while True:
                conn, addr = s.accept()
                with conn:
                    print(f"Connected by {addr}")
                    data = conn.recv(1024)
                    if data == self.get_current_command:
                        # Call the specific measure_current() method defined in subclasses
                        current = self.measure_current()
                        conn.sendall(str(current).encode('utf-8'))

    @property
    @abstractmethod
    def get_current_command(self) -> bytes:
        """
        This property must be implemented by each subclass to provide the specific
        command to get the current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

    @abstractmethod
    def measure_current(self) -> float:
        """
        This method must be implemented by each subclass to provide the specific
        logic for current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

