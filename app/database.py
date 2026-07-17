import json
import os
import sqlite3
from app.config import DATABASE_PATH
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")


def fecha_argentina():
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M:%S")


def obtener_ruta_db():
    return Path(
        os.getenv(
            "DATABASE_PATH",
            str(DATABASE_PATH)
        )
    )


def conectar():
    ruta_db = obtener_ruta_db()
    ruta_db.parent.mkdir(parents=True, exist_ok=True)

    return sqlite3.connect(ruta_db)


def inicializar():
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS facturas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden INTEGER UNIQUE,
            cliente TEXT,
            numero_factura INTEGER,
            total REAL,
            cae TEXT,
            vencimiento TEXT,
            estado TEXT,
            fecha TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            tipo TEXT,
            mensaje TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS errores_facturacion(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            orden INTEGER,
            cliente TEXT,
            total REAL,
            error TEXT,
            payload TEXT,
            estado TEXT
        )
        """)

        conn.commit()

    finally:
        conn.close()


def registrar_evento(tipo, mensaje):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO eventos(fecha, tipo, mensaje)
            VALUES (?, ?, ?)
            """,
            (
                fecha_argentina(),
                tipo,
                mensaje
            )
        )

        conn.commit()

    finally:
        conn.close()


def ultimos_eventos(limite=15):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT fecha, tipo, mensaje
            FROM eventos
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,)
        )

        return cur.fetchall()

    finally:
        conn.close()


def existe_orden_facturada(orden):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, numero_factura, cae
            FROM facturas
            WHERE orden = ?
            """,
            (orden,)
        )

        return cur.fetchone()

    finally:
        conn.close()


def guardar_factura(
    orden,
    cliente,
    numero_factura,
    total,
    cae,
    vencimiento,
    estado
):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO facturas(
                orden,
                cliente,
                numero_factura,
                total,
                cae,
                vencimiento,
                estado,
                fecha
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                orden,
                cliente,
                numero_factura,
                total,
                cae,
                vencimiento,
                estado,
                fecha_argentina()
            )
        )

        conn.commit()

    finally:
        conn.close()


def registrar_error_facturacion(
    orden,
    cliente,
    total,
    error,
    payload
):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO errores_facturacion(
                fecha,
                orden,
                cliente,
                total,
                error,
                payload,
                estado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fecha_argentina(),
                orden,
                cliente,
                total,
                str(error),
                json.dumps(payload, ensure_ascii=False),
                "pendiente"
            )
        )

        conn.commit()

    finally:
        conn.close()


def ultimos_errores_facturacion(limite=100):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                fecha,
                orden,
                cliente,
                total,
                error,
                estado
            FROM errores_facturacion
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,)
        )

        return cur.fetchall()

    finally:
        conn.close()


def obtener_error_facturacion(id_error):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                orden,
                cliente,
                total,
                error,
                payload,
                estado
            FROM errores_facturacion
            WHERE id = ?
            """,
            (id_error,)
        )

        dato = cur.fetchone()

    finally:
        conn.close()

    if not dato:
        return None

    return {
        "id": dato[0],
        "orden": dato[1],
        "cliente": dato[2],
        "total": dato[3],
        "error": dato[4],
        "payload": json.loads(dato[5]),
        "estado": dato[6]
    }


def marcar_error_resuelto(id_error):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE errores_facturacion
            SET estado = 'resuelto'
            WHERE id = ?
            """,
            (id_error,)
        )

        conn.commit()

    finally:
        conn.close()


def contar_facturas():
    conn = conectar()

    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facturas")

        return cur.fetchone()[0]

    finally:
        conn.close()


def contar_errores():
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM eventos
            WHERE tipo = 'ERROR'
            """
        )

        return cur.fetchone()[0]

    finally:
        conn.close()


def contar_pendientes():
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM errores_facturacion
            WHERE estado = 'pendiente'
            """
        )

        return cur.fetchone()[0]

    finally:
        conn.close()


def ultima_factura():
    conn = conectar()

    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(numero_factura) FROM facturas")

        resultado = cur.fetchone()[0]

        return resultado or 0

    finally:
        conn.close()


def ultimas_facturas(limite=10):
    conn = conectar()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                fecha,
                orden,
                cliente,
                numero_factura,
                total,
                cae,
                estado
            FROM facturas
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,)
        )

        return cur.fetchall()

    finally:
        conn.close()