"""Logging configuration for the backend process."""

import logging


def configure_logging() -> None:
    """Configure a consistent default logger for the process."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
