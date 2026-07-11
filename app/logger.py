import logging
import os

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("facturador")

logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter(

        "%(asctime)s | %(levelname)s | %(message)s"

    )

    archivo = logging.FileHandler(

        "logs/facturador.log",

        encoding="utf8"

    )

    archivo.setFormatter(formatter)

    logger.addHandler(archivo)