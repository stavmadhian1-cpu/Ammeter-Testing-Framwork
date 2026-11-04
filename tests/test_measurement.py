import contextlib
import io
import socket
import threading
import unittest

from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import read_current_from_ammeter
from src.testing.ammeters import Ammeter
from src.testing.results import SamplingSettings
from src.testing.sampling import run_sampling

COMMAND = b"MEASURE_TEST -get"


class FakeAmmeter:
    """
    A TCP server on a free port that answers the right command with the given replies, one per request,
    like the emulators. A wrong command gets no reply.
    """

    def __init__(self, replies: list):
        self.replies = list(replies)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("localhost", 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return  # Closed
            with connection:
                if connection.recv(1024) == COMMAND and self.replies:
                    connection.sendall(self.replies.pop(0))

    def close(self):
        self.server.close()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class ClientTest(unittest.TestCase):

    def setUp(self):
        self.ammeter = FakeAmmeter([b"1.25"])

    def tearDown(self):
        self.ammeter.close()

    def test_reads_the_current(self):
        self.assertEqual(read_current_from_ammeter(self.ammeter.port, COMMAND), 1.25)

    def test_wrong_command_gives_value_error(self):
        with self.assertRaisesRegex(ValueError, "No data received"):
            read_current_from_ammeter(self.ammeter.port, b"WRONG")

    def test_no_ammeter_gives_os_error(self):
        with self.assertRaises(OSError):
            read_current_from_ammeter(free_port(), COMMAND, timeout=0.5)


class SamplingTest(unittest.TestCase):

    def test_failed_measurements_are_recorded_and_the_test_continues(self):
        fake = FakeAmmeter([b"1.0", b"not a number", b"3.0"])
        try:
            ammeter = Ammeter("fake", "Fake", fake.port, COMMAND, "test")
            run = run_sampling([ammeter], SamplingSettings.from_values(count=4, frequency=20))
        finally:
            fake.close()
        result = run.results["fake"]
        self.assertEqual(result.currents, [1.0, 3.0])
        self.assertEqual(len(result.errors), 2)  # The invalid value and the request with no reply left
        self.assertTrue(result.errors[0].startswith("Measurement 2:"))
        self.assertEqual(result.attempted, 4)
        self.assertIsNotNone(result.late_count)


class GreenleeOutputTest(unittest.TestCase):

    def test_measuring_works_when_the_output_is_not_utf8(self):
        # Regression test for FIXES.md, Fix 5: printing the Ohm symbol crashed the emulator
        output = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with contextlib.redirect_stdout(output):
            current = GreenleeAmmeter(port=0).measure_current()
        self.assertGreater(current, 0)


if __name__ == "__main__":
    unittest.main()
