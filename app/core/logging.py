import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers = [handler]

    # Quiet noisy third-party loggers unless we're actively debugging.
    access_level = logging.INFO if settings.debug else logging.WARNING
    logging.getLogger("uvicorn.access").setLevel(access_level)
