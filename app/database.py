import sqlite3
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB = Path("data/facturador.db")
DB.parent.mkdir(exist_ok=True)

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")


def fecha_argentina():
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M:%S")


def conectar():
    return sqlite3.connect(DB)


def inicializar():
    conn = conectar()
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
    conn.close()


def registrar_evento(tipo, mensaje):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO eventos(fecha, tipo, mensaje) VALUES(?, ?, ?)",
        (fecha_argentina(), tipo, mensaje)
    )

    conn.commit()
    conn.close()


def ultimos_eventos(limite=15):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT fecha, tipo, mensaje
        FROM eventos
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))

    datos = cur.fetchall()
    conn.close()

    return datos


def existe_orden_facturada(orden):
    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, numero_factura, cae FROM facturas WHERE orden = ?",
        (orden,)
    )

    resultado = cur.fetchone()
    conn.close()

    return resultado


def guardar_factura(orden, cliente, numero_factura, total, cae, vencimiento, estado):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
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
    """, (
        orden,
        cliente,
        numero_factura,
        total,
        cae,
        vencimiento,
        estado,
        fecha_argentina()
    ))

    conn.commit()
    conn.close()


def registrar_error_facturacion(orden, cliente, total, error, payload):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
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
    """, (
        fecha_argentina(),
        orden,
        cliente,
        total,
        str(error),
        json.dumps(payload, ensure_ascii=False),
        "pendiente"
    ))

    conn.commit()
    conn.close()


def ultimos_errores_facturacion(limite=100):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, fecha, orden, cliente, total, error, estado
        FROM errores_facturacion
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))

    datos = cur.fetchall()
    conn.close()

    return datos


def obtener_error_facturacion(id_error):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, orden, cliente, total, error, payload, estado
        FROM errores_facturacion
        WHERE id = ?
    """, (id_error,))

    dato = cur.fetchone()
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
    cur = conn.cursor()

    cur.execute("""
        UPDATE errores_facturacion
        SET estado = 'resuelto'
        WHERE id = ?
    """, (id_error,))

    conn.commit()
    conn.close()


def contar_facturas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM facturas")
    total = cur.fetchone()[0]

    conn.close()
    return total


def contar_errores():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM eventos WHERE tipo = 'ERROR'")
    total = cur.fetchone()[0]

    conn.close()
    return total


def contar_pendientes():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM errores_facturacion
        WHERE estado = 'pendiente'
    """)

    total = cur.fetchone()[0]

    conn.close()
    return total


def ultima_factura():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT MAX(numero_factura) FROM facturas")
    resultado = cur.fetchone()[0]

    conn.close()
    return resultado or 0


def ultimas_facturas(limite=10):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT fecha, orden, cliente, numero_factura, total, cae, estado
        FROM facturas
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))

    datos = cur.fetchall()
    conn.close()

    return datos