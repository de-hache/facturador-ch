import logging
from logging.handlers import RotatingFileHandler

from app.config import (
    LOG_BACKUP_COUNT,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_PATH,
)


LOG_PATH.mkdir(
    parents=True,
    exist_ok=True,
)

ARCHIVO_LOG = LOG_PATH / "facturador.log"


logger = logging.getLogger(
    "chuli_facturador"
)

logger.setLevel(
    getattr(
        logging,
        LOG_LEVEL,
        logging.INFO,
    )
)

logger.propagate = False


if not logger.handlers:
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    manejador_archivo = RotatingFileHandler(
        ARCHIVO_LOG,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    manejador_archivo.setFormatter(
        formato
    )

    manejador_consola = logging.StreamHandler()
    manejador_consola.setFormatter(
        formato
    )

    logger.addHandler(
        manejador_archivo
    )

    logger.addHandler(
        manejador_consola
    )