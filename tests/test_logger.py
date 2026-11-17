
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.logger import setup_logger


class LoggerTests(unittest.TestCase):
    def test_creates_log_directory_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_file = log_dir / "app.log"

            with (
                patch("app.logger.LOG_DIR", log_dir),
                patch("app.logger.LOG_FILE", log_file),
            ):
                logger = logging.getLogger("test_logger")

                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                    handler.close()

                with patch("app.logger.logging.getLogger", return_value=logger):
                    configured_logger = setup_logger()

                configured_logger.info("Test log message")

                for handler in configured_logger.handlers:
                    handler.flush()

                self.assertTrue(log_dir.exists())
                self.assertTrue(log_file.exists())
                self.assertIn(
                    "Test log message",
                    log_file.read_text(encoding="utf-8"),
                )

                for handler in configured_logger.handlers[:]:
                    configured_logger.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
