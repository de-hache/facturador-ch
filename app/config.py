import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def obtener_bool(
    nombre: str,
    valor_por_defecto: bool = False,
) -> bool:
    valor = os.getenv(nombre)

    if valor is None:
        return valor_por_defecto

    return valor.strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
        "on",
    }


def obtener_entero(
    nombre: str,
    valor_por_defecto: int,
) -> int:
    valor = os.getenv(nombre)

    if valor is None or not valor.strip():
        return valor_por_defecto

    try:
        return int(valor)

    except ValueError as error:
        raise RuntimeError(
            f"La variable {nombre} debe contener un número entero."
        ) from error


APP_NAME = os.getenv(
    "APP_NAME",
    "Chuli-Facturador",
)

APP_ENV = os.getenv(
    "APP_ENV",
    "development",
)

APP_DEBUG = obtener_bool(
    "APP_DEBUG",
    True,
)

APP_HOST = os.getenv(
    "APP_HOST",
    "127.0.0.1",
)

APP_PORT = obtener_entero(
    "APP_PORT",
    8000,
)

CUIT = os.getenv("CUIT")

AFIP_PRODUCTION = obtener_bool(
    "AFIP_PRODUCTION",
    False,
)

AFIP_ACCESS_TOKEN = os.getenv(
    "AFIP_ACCESS_TOKEN"
)

AFIP_CERT_PATH = Path(
    os.getenv(
        "AFIP_CERT_PATH",
        "certificado.crt",
    )
)

AFIP_KEY_PATH = Path(
    os.getenv(
        "AFIP_KEY_PATH",
        "privada.key",
    )
)

PUNTO_VENTA = obtener_entero(
    "PUNTO_VENTA",
    1,
)

TIPO_COMPROBANTE = obtener_entero(
    "TIPO_COMPROBANTE",
    11,
)

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        "data/facturador.db",
    )
)

VENTAS_PATH = Path(
    os.getenv(
        "VENTAS_PATH",
        "ventas",
    )
)

LOG_PATH = Path(
    os.getenv(
        "LOG_PATH",
        "logs",
    )
)

ULTIMO_PROCESO_PATH = Path(
    os.getenv(
        "ULTIMO_PROCESO_PATH",
        "logs/ultimo_proceso.txt",
    )
)

ARCA_MAX_REINTENTOS = obtener_entero(
    "ARCA_MAX_REINTENTOS",
    4,
)

ARCA_ESPERAS = [
    obtener_entero(
        "ARCA_REINTENTO_1_SEGUNDOS",
        5,
    ),
    obtener_entero(
        "ARCA_REINTENTO_2_SEGUNDOS",
        10,
    ),
    obtener_entero(
        "ARCA_REINTENTO_3_SEGUNDOS",
        20,
    ),
    obtener_entero(
        "ARCA_REINTENTO_4_SEGUNDOS",
        40,
    ),
]

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()

LOG_MAX_BYTES = obtener_entero(
    "LOG_MAX_BYTES",
    5_242_880,
)

LOG_BACKUP_COUNT = obtener_entero(
    "LOG_BACKUP_COUNT",
    5,
)


def validar_configuracion() -> None:
    errores = []

    if not CUIT:
        errores.append(
            "Falta configurar CUIT en .env"
        )

    elif not CUIT.isdigit():
        errores.append(
            "CUIT debe contener solo números"
        )

    if not AFIP_ACCESS_TOKEN:
        errores.append(
            "Falta configurar AFIP_ACCESS_TOKEN en .env"
        )

    if not AFIP_CERT_PATH.exists():
        errores.append(
            f"No se encontró el certificado: {AFIP_CERT_PATH}"
        )

    if not AFIP_KEY_PATH.exists():
        errores.append(
            f"No se encontró la clave privada: {AFIP_KEY_PATH}"
        )

    if errores:
        detalle = "\n- ".join(errores)

        raise RuntimeError(
            "Configuración incompleta:\n- "
            + detalle
        )