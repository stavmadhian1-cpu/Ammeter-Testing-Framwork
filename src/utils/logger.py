import itertools
import logging
import os
from datetime import datetime
from pathlib import Path

# results/logs in the project root, so logs are saved in the same place from any working directory
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "results" / "logs"

_instances = itertools.count()  # Gives each logger its own name, so two tests never share a log file


class TestLogger:
    """
    Writes the messages of one test to its own log file: <log_dir>/<date>_<time>_<test name>.log
    Call `close()` when the test ends, so the file is released.
    """

    def __init__(self, test_name: str, log_dir=DEFAULT_LOG_DIR):
        self._test_name = test_name
        self._log_dir = Path(log_dir)
        self.log_file = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """
        Sets up the logger with a time stamp and level on every line, writing to a file.
        """
        os.makedirs(self._log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self._log_dir / f"{timestamp}_{self._test_name}.log"

        logger = logging.getLogger(f"test_{self._test_name}_{next(_instances)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Only to the file, not to the terminal
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
        logger.addHandler(handler)
        return logger

    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)

    def debug(self, message: str):
        self.logger.debug(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def close(self):
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
