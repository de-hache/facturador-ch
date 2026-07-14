import sqlite3

import pytest

from app.database import (
    conectar,
    contar_facturas,
    contar_pendientes,
    existe_orden_facturada,
    guardar_factura,
    inicializar,
    marcar_error_resuelto,
    obtener_error_facturacion,
    registrar_error_facturacion,
    registrar_evento,
    ultimos_eventos
)


@pytest.fixture
def base_temporal(tmp_path, monkeypatch):
    """
    Crea una base SQLite aislada para cada prueba.

    No utiliza ni modifica data/facturador.db.
    """
    ruta_db = tmp_path / "facturador_test.db"

    monkeypatch.setenv(
        "DATABASE_PATH",
        str(ruta_db)
    )

    inicializar()

    return ruta_db


def test_inicializar_crea_base_y_tablas(base_temporal):
    assert base_temporal.exists()

    conn = sqlite3.connect(base_temporal)

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)

        tablas = {
            fila[0]
            for fila in cur.fetchall()
        }

    finally:
        conn.close()

    assert "facturas" in tablas
    assert "eventos" in tablas
    assert "errores_facturacion" in tablas


def test_conectar_utiliza_base_temporal(base_temporal):
    conn = conectar()

    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")

        resultado = cur.fetchone()[0]

    finally:
        conn.close()

    assert resultado == 1


def test_guardar_y_detectar_factura(base_temporal):
    guardar_factura(
        orden=1001,
        cliente="Cliente de prueba",
        numero_factura=25,
        total=15000.50,
        cae="12345678901234",
        vencimiento="20260731",
        estado="Emitida"
    )

    factura = existe_orden_facturada(1001)

    assert factura is not None
    assert factura[1] == 25
    assert factura[2] == "12345678901234"
    assert contar_facturas() == 1


def test_orden_inexistente_devuelve_none(base_temporal):
    resultado = existe_orden_facturada(9999)

    assert resultado is None


def test_no_permite_orden_duplicada(base_temporal):
    guardar_factura(
        orden=2001,
        cliente="Primera factura",
        numero_factura=30,
        total=5000,
        cae="11111111111111",
        vencimiento="20260731",
        estado="Emitida"
    )

    with pytest.raises(sqlite3.IntegrityError):
        guardar_factura(
            orden=2001,
            cliente="Factura duplicada",
            numero_factura=31,
            total=5000,
            cae="22222222222222",
            vencimiento="20260731",
            estado="Emitida"
        )

    assert contar_facturas() == 1


def test_registrar_evento(base_temporal):
    registrar_evento(
        "INFO",
        "Evento generado desde pytest"
    )

    eventos = ultimos_eventos(10)

    assert len(eventos) == 1
    assert eventos[0][1] == "INFO"
    assert eventos[0][2] == "Evento generado desde pytest"


def test_registrar_pendiente(base_temporal):
    payload = {
        "id_orden": 3001,
        "cliente": {
            "nombre": "Cliente pendiente"
        },
        "total": 25000
    }

    registrar_error_facturacion(
        orden=3001,
        cliente="Cliente pendiente",
        total=25000,
        error="Servidor temporalmente no disponible",
        payload=payload
    )

    assert contar_pendientes() == 1

    pendiente = obtener_error_facturacion(1)

    assert pendiente is not None
    assert pendiente["orden"] == 3001
    assert pendiente["estado"] == "pendiente"
    assert pendiente["payload"]["id_orden"] == 3001


def test_marcar_pendiente_como_resuelto(base_temporal):
    registrar_error_facturacion(
        orden=4001,
        cliente="Cliente reprocesado",
        total=30000,
        error="Error temporal",
        payload={
            "id_orden": 4001,
            "total": 30000
        }
    )

    pendiente = obtener_error_facturacion(1)

    assert pendiente["estado"] == "pendiente"

    marcar_error_resuelto(1)

    pendiente_resuelto = obtener_error_facturacion(1)

    assert pendiente_resuelto["estado"] == "resuelto"
    assert contar_pendientes() == 0