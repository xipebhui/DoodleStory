import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_LOG_FILE = PROJECT_ROOT / "backend" / "logs" / "local-backend.log"


def _has_file_handler(root_logger: logging.Logger, log_file: Path) -> bool:
    return any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_file
        for handler in root_logger.handlers
    )


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    for handler in root_logger.handlers:
        handler.setLevel(level)

    BACKEND_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _has_file_handler(root_logger, BACKEND_LOG_FILE):
        file_handler = logging.FileHandler(BACKEND_LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    for logger_name in ("app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).setLevel(level)
