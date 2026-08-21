import logging
import sys

from app.core.config import settings

_NOISY_LOGGERS = (
    "google",
    "google.auth",
    "google.api_core",
    "urllib3",
    "httpcore",
    "httpx",
)


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
