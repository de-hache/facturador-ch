import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import (
    BACKUP_KEEP_COUNT,
    BACKUP_PATH,
    DATABASE_PATH,
)
from app.logger import logger


def crear_backup_sqlite() -> Path:
    BACKUP_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE_PATH}"
        )

    fecha = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    archivo_backup = (
        BACKUP_PATH
        / f"facturador_{fecha}.db"
    )

    with sqlite3.connect(DATABASE_PATH) as origen:
        with sqlite3.connect(archivo_backup) as destino:
            origen.backup(destino)

    logger.info(
        "Backup SQLite creado: %s",
        archivo_backup,
    )

    limpiar_backups_antiguos()

    return archivo_backup


def limpiar_backups_antiguos() -> None:
    if not BACKUP_PATH.exists():
        return

    backups = sorted(
        BACKUP_PATH.glob("facturador_*.db"),
        key=lambda archivo: archivo.stat().st_mtime,
        reverse=True,
    )

    for archivo in backups[BACKUP_KEEP_COUNT:]:
        archivo.unlink()

        logger.info(
            "Backup antiguo eliminado: %s",
            archivo,
        )