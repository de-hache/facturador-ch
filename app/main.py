import datetime
import os
import subprocess
import sys
import time
from html import escape
from pathlib import Path

from afip import Afip
from fastapi import FastAPI, Form, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    AFIP_ACCESS_TOKEN,
    AFIP_CERT_PATH,
    AFIP_KEY_PATH,
    AFIP_PRODUCTION,
    APP_NAME,
    ARCA_ESPERAS,
    ARCA_MAX_REINTENTOS,
    CUIT,
    PUNTO_VENTA,
    TIPO_COMPROBANTE,
    ULTIMO_PROCESO_PATH,
    VENTAS_PATH,
    validar_configuracion,
)
from app.database import (
    contar_errores,
    contar_facturas,
    contar_pendientes,
    existe_orden_facturada,
    guardar_factura,
    inicializar,
    marcar_error_resuelto,
    obtener_error_facturacion,
    registrar_error_facturacion,
    registrar_evento,
    ultima_factura,
    ultimas_facturas,
    ultimos_errores_facturacion,
    ultimos_eventos,
)
from app.errors import (
    manejar_error_404,
    manejar_error_general,
    manejar_error_validacion,
)
from app.logger import logger


# =====================================================
# APLICACIÓN FASTAPI
# =====================================================

app = FastAPI(title=APP_NAME)


app.add_exception_handler(
    404,
    manejar_error_404,
)

app.add_exception_handler(
    RequestValidationError,
    manejar_error_validacion,
)

app.add_exception_handler(
    Exception,
    manejar_error_general,
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# =====================================================
# INICIALIZACIÓN
# =====================================================

inicializar()

logger.info("Servidor iniciado")
registrar_evento(
    "INFO",
    "Servidor iniciado",
)


# =====================================================
# CARPETAS Y ARCHIVOS
# =====================================================

LOG_PROCESO = ULTIMO_PROCESO_PATH

LOG_PROCESO.parent.mkdir(
    parents=True,
    exist_ok=True,
)


CARPETA_VENTAS = VENTAS_PATH

CARPETA_VENTAS.mkdir(
    parents=True,
    exist_ok=True,
)


FAVICON = (
    "https://d22fxaf9t8d39k.cloudfront.net/"
    "1dfabd14f4725ee6bceb4fbfccfd8acfc2995aef483ad49a1407d95fc2d86d29140661.png"
)


# =====================================================
# FUNCIONES GENERALES
# =====================================================

def head_html(
    titulo: str = APP_NAME,
) -> str:
    return f"""
    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>{escape(titulo)}</title>

        <link
            rel="shortcut icon"
            href="{FAVICON}"
        >

        <link
            rel="stylesheet"
            href="/static/css/style.css"
        >
    </head>
    """


def leer_ultimo_proceso() -> str:
    if LOG_PROCESO.exists():
        return LOG_PROCESO.read_text(
            encoding="utf-8",
            errors="replace",
        )

    return "Todavía no se ejecutó ningún proceso."


def guardar_ultimo_proceso(
    texto: str,
) -> None:
    LOG_PROCESO.write_text(
        texto,
        encoding="utf-8",
    )


def listar_csv_ventas() -> list[str]:
    archivos = []

    for archivo in CARPETA_VENTAS.glob("*.csv"):
        ruta_normalizada = str(
            archivo
        ).replace(
            "\\",
            "/",
        )

        archivos.append(
            ruta_normalizada
        )

    return sorted(archivos)


# =====================================================
# CONFIGURACIÓN ARCA / AFIP
# =====================================================

validar_configuracion()


with open(
    AFIP_CERT_PATH,
    "r",
    encoding="utf-8",
) as archivo_certificado:
    contenido_certificado = (
        archivo_certificado.read()
    )


with open(
    AFIP_KEY_PATH,
    "r",
    encoding="utf-8",
) as archivo_clave:
    contenido_llave = archivo_clave.read()


afip = Afip({
    "CUIT": int(CUIT),
    "cert": contenido_certificado,
    "key": contenido_llave,
    "production": AFIP_PRODUCTION,
    "access_token": AFIP_ACCESS_TOKEN,
})


# =====================================================
# REINTENTOS ARCA
# =====================================================

def es_error_temporal(
    error: Exception,
) -> bool:
    mensaje = str(error).lower()

    palabras_temporales = [
        "congestion",
        "congestionado",
        "temporarily",
        "timeout",
        "timed out",
        "service unavailable",
        "server error",
        "503",
        "502",
        "504",
        "connection",
        "servidor",
        "no disponible",
    ]

    return any(
        palabra in mensaje
        for palabra in palabras_temporales
    )


def crear_voucher_con_reintentos(
    data_afip: dict,
    id_orden: int,
    numero_factura: int,
    intentos: int | None = None,
):
    if intentos is None:
        intentos = ARCA_MAX_REINTENTOS

    if intentos < 1:
        raise RuntimeError(
            "ARCA_MAX_REINTENTOS debe ser "
            "igual o mayor a 1."
        )

    ultimo_error = None

    for intento in range(intentos):
        numero_intento = intento + 1

        try:
            registrar_evento(
                "INFO",
                (
                    f"Intento {numero_intento}/{intentos} - "
                    f"Solicitando CAE para orden {id_orden}, "
                    f"factura {numero_factura}"
                ),
            )

            resultado = (
                afip
                .ElectronicBilling
                .createVoucher(
                    data_afip
                )
            )

            registrar_evento(
                "INFO",
                (
                    f"CAE obtenido en intento "
                    f"{numero_intento} - "
                    f"Orden {id_orden}"
                ),
            )

            return resultado

        except Exception as error:
            ultimo_error = error

            quedan_intentos = (
                intento < intentos - 1
            )

            if (
                es_error_temporal(error)
                and quedan_intentos
            ):
                indice_espera = min(
                    intento,
                    len(ARCA_ESPERAS) - 1,
                )

                segundos = (
                    ARCA_ESPERAS[
                        indice_espera
                    ]
                )

                registrar_evento(
                    "ERROR",
                    (
                        "Error temporal de ARCA "
                        f"en orden {id_orden}. "
                        f"Reintentando en {segundos} "
                        "segundos. "
                        f"Detalle: {error}"
                    ),
                )

                logger.warning(
                    (
                        "Error temporal de ARCA "
                        "en orden %s. "
                        "Reintento en %s segundos. "
                        "Detalle: %s"
                    ),
                    id_orden,
                    segundos,
                    error,
                )

                time.sleep(segundos)
                continue

            registrar_evento(
                "ERROR",
                (
                    "No se pudo obtener CAE "
                    f"para orden {id_orden}. "
                    f"Error final: {error}"
                ),
            )

            logger.exception(
                (
                    "No se pudo obtener CAE "
                    "para la orden %s"
                ),
                id_orden,
            )

            raise

    if ultimo_error:
        raise ultimo_error

    raise RuntimeError(
        f"No se pudo procesar la orden {id_orden}."
    )


# =====================================================
# DASHBOARD
# =====================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def dashboard():
    total_facturas = contar_facturas()
    total_errores = contar_errores()
    total_pendientes = contar_pendientes()
    ultima = ultima_factura()

    eventos = ultimos_eventos()
    facturas = ultimas_facturas()
    archivos_csv = listar_csv_ventas()

    salida_proceso = escape(
        leer_ultimo_proceso()
    )

    modo_arca = (
        "Producción"
        if AFIP_PRODUCTION
        else "Homologación"
    )

    opciones_csv = ""

    if archivos_csv:
        for archivo in archivos_csv:
            archivo_seguro = escape(
                archivo,
                quote=True,
            )

            opciones_csv += f"""
                <option value="{archivo_seguro}">
                    {archivo_seguro}
                </option>
            """
    else:
        opciones_csv = """
            <option value="">
                No hay archivos CSV en la carpeta ventas/
            </option>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">

    {head_html(APP_NAME)}

    <body>
        <div class="contenedor">

            <div class="header">
                <div>
                    <h1>🧾 {escape(APP_NAME)}</h1>

                    <p>
                        Dashboard ARCA / AFIP ·
                        Modo: {escape(modo_arca)}
                    </p>
                </div>
            </div>

            <div class="grid">

                <div class="card">
                    <h3>Servidor</h3>

                    <div class="numero ok">
                        ONLINE
                    </div>
                </div>

                <div class="card">
                    <h3>SQLite</h3>

                    <div class="numero ok">
                        OK
                    </div>
                </div>

                <div class="card">
                    <h3>Facturas</h3>

                    <div class="numero">
                        {total_facturas}
                    </div>
                </div>

                <div class="card">
                    <h3>Errores</h3>

                    <div class="numero error">
                        {total_errores}
                    </div>
                </div>

                <div class="card">
                    <h3>Pendientes</h3>

                    <div class="numero error">
                        {total_pendientes}
                    </div>
                </div>

            </div>

            <div class="card">
                <h3>Última factura emitida</h3>

                <div class="numero">
                    #{ultima}
                </div>

                <br>

                <a
                    class="boton-secundario"
                    href="/db/facturas"
                >
                    Ver facturas SQLite
                </a>

                <a
                    class="boton-secundario"
                    href="/db/eventos"
                >
                    Ver eventos SQLite
                </a>

                <a
                    class="boton-secundario"
                    href="/db/errores"
                >
                    Ver pendientes
                </a>

                <br><br>

                <form
                    action="/procesar"
                    method="post"
                >
                    <label>
                        <b>Seleccionar archivo CSV:</b>
                    </label>

                    <br><br>

                    <select
                        name="archivo_csv"
                        required
                    >
                        {opciones_csv}
                    </select>

                    <br><br>

                    <button
                        class="boton"
                        type="submit"
                    >
                        ▶ Procesar lote seleccionado
                    </button>
                </form>

                <div class="aviso">
                    Los archivos CSV deben estar dentro de
                    <b>{escape(str(CARPETA_VENTAS))}/</b>.

                    Nomenclatura recomendada:
                    <b>AAAA-MM-DD_a_AAAA-MM-DD.csv</b>
                </div>
            </div>

            <div class="card seccion">
                <h2>Consola del último proceso</h2>

                <div class="consola">
                    {salida_proceso}
                </div>
            </div>

            <div class="card seccion">
                <h2>Últimas facturas emitidas</h2>

                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Orden</th>
                        <th>Cliente</th>
                        <th>Factura</th>
                        <th>Total</th>
                        <th>CAE</th>
                        <th>Estado</th>
                        <th>Consulta</th>
                    </tr>
    """

    for factura in facturas:
        fecha = escape(
            str(factura[0])
        )

        orden = escape(
            str(factura[1])
        )

        cliente = escape(
            str(factura[2])
        )

        numero_factura = factura[3]

        total = escape(
            str(factura[4])
        )

        cae = escape(
            str(factura[5])
        )

        estado_factura = escape(
            str(factura[6])
        )

        html += f"""
                    <tr>
                        <td>{fecha}</td>
                        <td>{orden}</td>
                        <td>{cliente}</td>
                        <td>{numero_factura}</td>
                        <td>${total}</td>
                        <td>{cae}</td>
                        <td>{estado_factura}</td>

                        <td>
                            <a
                                href="/consultar/{numero_factura}"
                                target="_blank"
                            >
                                Ver en ARCA
                            </a>
                        </td>
                    </tr>
        """

    html += """
                </table>
            </div>

            <div class="card seccion">
                <h2>Últimos eventos</h2>

                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Tipo</th>
                        <th>Mensaje</th>
                    </tr>
    """

    for evento in eventos:
        fecha = escape(
            str(evento[0])
        )

        tipo = escape(
            str(evento[1])
        )

        mensaje = escape(
            str(evento[2])
        )

        clase = (
            "tipo-error"
            if evento[1] == "ERROR"
            else "tipo-info"
        )

        html += f"""
                    <tr>
                        <td>{fecha}</td>

                        <td class="{clase}">
                            {tipo}
                        </td>

                        <td>{mensaje}</td>
                    </tr>
        """

    html += """
                </table>
            </div>

        </div>
    </body>
    </html>
    """

    return HTMLResponse(html)


# =====================================================
# PROCESAR CSV SELECCIONADO
# =====================================================

@app.post("/procesar")
def procesar(
    archivo_csv: str = Form(...),
):
    if not archivo_csv:
        mensaje = (
            "No se seleccionó ningún archivo CSV."
        )

        guardar_ultimo_proceso(
            mensaje
        )

        registrar_evento(
            "ERROR",
            mensaje,
        )

        logger.warning(mensaje)

        return RedirectResponse(
            "/",
            status_code=303,
        )

    try:
        ruta = Path(
            archivo_csv
        ).resolve()

        carpeta_ventas_resuelta = (
            CARPETA_VENTAS.resolve()
        )

        try:
            ruta.relative_to(
                carpeta_ventas_resuelta
            )

        except ValueError:
            mensaje = (
                "El archivo seleccionado no pertenece "
                "a la carpeta de ventas."
            )

            guardar_ultimo_proceso(
                mensaje
            )

            registrar_evento(
                "ERROR",
                mensaje,
            )

            logger.warning(mensaje)

            return RedirectResponse(
                "/",
                status_code=303,
            )

        if not ruta.exists():
            mensaje = (
                "El archivo seleccionado no existe: "
                f"{archivo_csv}"
            )

            guardar_ultimo_proceso(
                mensaje
            )

            registrar_evento(
                "ERROR",
                mensaje,
            )

            logger.warning(mensaje)

            return RedirectResponse(
                "/",
                status_code=303,
            )

        if ruta.suffix.lower() != ".csv":
            mensaje = (
                "El archivo seleccionado debe tener "
                "extensión .csv."
            )

            guardar_ultimo_proceso(
                mensaje
            )

            registrar_evento(
                "ERROR",
                mensaje,
            )

            logger.warning(mensaje)

            return RedirectResponse(
                "/",
                status_code=303,
            )

        registrar_evento(
            "INFO",
            (
                "Procesamiento iniciado "
                "desde Dashboard: "
                f"{archivo_csv}"
            ),
        )

        logger.info(
            (
                "Procesamiento iniciado "
                "desde Dashboard: %s"
            ),
            archivo_csv,
        )

        entorno = os.environ.copy()
        entorno["PYTHONIOENCODING"] = "utf-8"

        resultado = subprocess.run(
            [
                sys.executable,
                "procesar_lote.py",
                str(ruta),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=entorno,
            check=False,
        )

        salida = (
            "========== STDOUT ==========\n"
            f"{resultado.stdout or ''}"
            "\n\n========== STDERR ==========\n"
            f"{resultado.stderr or ''}"
            "\n\n========== CÓDIGO DE SALIDA: "
            f"{resultado.returncode} ==========\n"
        )

        guardar_ultimo_proceso(
            salida
        )

        if resultado.returncode == 0:
            registrar_evento(
                "INFO",
                (
                    "Proceso finalizado correctamente: "
                    f"{archivo_csv}"
                ),
            )

            logger.info(
                "Proceso finalizado correctamente: %s",
                archivo_csv,
            )

        else:
            registrar_evento(
                "ERROR",
                (
                    "El proceso terminó con error: "
                    f"{archivo_csv}"
                ),
            )

            logger.error(
                (
                    "El procesamiento terminó "
                    "con código %s: %s"
                ),
                resultado.returncode,
                archivo_csv,
            )

    except Exception as error:
        mensaje = (
            "Error ejecutando procesar_lote.py."
        )

        guardar_ultimo_proceso(
            mensaje
        )

        registrar_evento(
            "ERROR",
            mensaje,
        )

        logger.exception(
            (
                "Error ejecutando "
                "procesar_lote.py: %s"
            ),
            error,
        )

    return RedirectResponse(
        "/",
        status_code=303,
    )


# =====================================================
# WEBHOOK DE FACTURACIÓN
# =====================================================

@app.post("/webhook-empretienda")
def recibir_venta(
    datos_venta: dict,
):
    try:
        id_orden = int(
            datos_venta["id_orden"]
        )

        cliente = str(
            datos_venta["cliente"]["nombre"]
        )

        total = round(
            float(datos_venta["total"]),
            2,
        )

        factura_existente = (
            existe_orden_facturada(
                id_orden
            )
        )

        if factura_existente:
            numero_factura_existente = (
                factura_existente[1]
            )

            cae_existente = (
                factura_existente[2]
            )

            registrar_evento(
                "INFO",
                (
                    f"Orden {id_orden} omitida: "
                    "ya fue facturada como comprobante "
                    f"{numero_factura_existente}"
                ),
            )

            logger.info(
                (
                    "Orden %s omitida porque ya "
                    "fue facturada como %s"
                ),
                id_orden,
                numero_factura_existente,
            )

            return {
                "status": "duplicada",
                "mensaje": (
                    "La orden ya fue facturada "
                    "anteriormente"
                ),
                "orden": id_orden,
                "factura": (
                    numero_factura_existente
                ),
                "CAE": cae_existente,
            }

        registrar_evento(
            "INFO",
            (
                f"Orden {id_orden} recibida - "
                f"{cliente} - ${total:.2f}"
            ),
        )

        logger.info(
            (
                "Orden %s recibida - "
                "%s - $%.2f"
            ),
            id_orden,
            cliente,
            total,
        )

        ultimo_numero = (
            afip
            .ElectronicBilling
            .getLastVoucher(
                PUNTO_VENTA,
                TIPO_COMPROBANTE,
            )
        )

        numero_nueva_factura = (
            ultimo_numero + 1
        )

        fecha_actual = (
            datetime.datetime.now()
            .strftime("%Y%m%d")
        )

        tipo_doc_cliente = str(
            datos_venta
            .get("cliente", {})
            .get("tipo_doc", "")
        ).strip().upper()

        if tipo_doc_cliente == "DNI":
            doc_tipo_afip = 96

        elif tipo_doc_cliente == "CUIT":
            doc_tipo_afip = 80

        else:
            doc_tipo_afip = 99

        dni_cuit = str(
            datos_venta
            .get("cliente", {})
            .get("dni_cuit", "")
        ).strip()

        documento_limpio = (
            dni_cuit
            .replace(".", "")
            .replace("-", "")
            .replace(" ", "")
        )

        if documento_limpio.isdigit():
            doc_nro = int(
                documento_limpio
            )

        else:
            doc_nro = 0
            doc_tipo_afip = 99

        condicion_iva_receptor = int(
            datos_venta.get(
                "CondicionIVAReceptorId",
                5,
            )
        )

        data_afip = {
            "CantReg": 1,
            "PtoVta": PUNTO_VENTA,
            "CbteTipo": TIPO_COMPROBANTE,
            "Concepto": 1,
            "DocTipo": doc_tipo_afip,
            "DocNro": doc_nro,
            "CbteDesde": numero_nueva_factura,
            "CbteHasta": numero_nueva_factura,
            "CbteFch": fecha_actual,
            "ImpTotal": total,
            "ImpTotConc": 0,
            "ImpNeto": total,
            "ImpOpEx": 0,
            "ImpTrib": 0,
            "ImpIVA": 0,
            "MonId": "PES",
            "MonCotiz": 1,
            "CondicionIVAReceptorId": (
                condicion_iva_receptor
            ),
        }

        resultado = (
            crear_voucher_con_reintentos(
                data_afip=data_afip,
                id_orden=id_orden,
                numero_factura=(
                    numero_nueva_factura
                ),
            )
        )

        cae = resultado.get("CAE")

        if not cae:
            raise RuntimeError(
                "ARCA no devolvió un CAE válido."
            )

        vencimiento = (
            resultado.get("CAEFchVto")
            or resultado.get("CAEFAreaVenc")
            or resultado.get("Vencimiento")
            or ""
        )

        guardar_factura(
            orden=id_orden,
            cliente=cliente,
            numero_factura=(
                numero_nueva_factura
            ),
            total=total,
            cae=cae,
            vencimiento=vencimiento,
            estado="Emitida",
        )

        registrar_evento(
            "INFO",
            (
                f"Factura {numero_nueva_factura} "
                "emitida correctamente - "
                f"Orden {id_orden}"
            ),
        )

        logger.info(
            (
                "Factura %s emitida correctamente "
                "para la orden %s"
            ),
            numero_nueva_factura,
            id_orden,
        )

        return {
            "status": "success",
            "orden": id_orden,
            "factura": numero_nueva_factura,
            "CAE": cae,
            "Vencimiento": vencimiento,
            "respuesta_completa": resultado,
        }

    except HTTPException:
        raise

    except Exception as error:
        id_orden_error = datos_venta.get(
            "id_orden",
            0,
        )

        cliente_error = (
            datos_venta
            .get("cliente", {})
            .get(
                "nombre",
                "Sin cliente",
            )
        )

        total_error = datos_venta.get(
            "total",
            0,
        )

        registrar_evento(
            "ERROR",
            (
                f"Error orden {id_orden_error}: "
                f"{error}"
            ),
        )

        registrar_error_facturacion(
            orden=id_orden_error,
            cliente=cliente_error,
            total=total_error,
            error=str(error),
            payload=datos_venta,
        )

        logger.exception(
            (
                "Error facturando la orden %s"
            ),
            id_orden_error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo completar la facturación. "
                "El error fue registrado."
            ),
        ) from error


# =====================================================
# REPROCESAR PENDIENTES
# =====================================================

@app.post(
    "/reprocesar-pendiente/{id_error}"
)
def reprocesar_pendiente(
    id_error: int,
):
    error_guardado = (
        obtener_error_facturacion(
            id_error
        )
    )

    if not error_guardado:
        registrar_evento(
            "ERROR",
            (
                "No se encontró pendiente "
                f"con ID {id_error}"
            ),
        )

        logger.warning(
            (
                "No se encontró pendiente "
                "con ID %s"
            ),
            id_error,
        )

        return RedirectResponse(
            "/db/errores",
            status_code=303,
        )

    if (
        error_guardado["estado"]
        != "pendiente"
    ):
        registrar_evento(
            "INFO",
            (
                f"El registro {id_error} "
                "ya no se encuentra pendiente"
            ),
        )

        logger.info(
            (
                "El registro %s ya no "
                "se encuentra pendiente"
            ),
            id_error,
        )

        return RedirectResponse(
            "/db/errores",
            status_code=303,
        )

    payload = error_guardado["payload"]
    orden = error_guardado["orden"]

    registrar_evento(
        "INFO",
        (
            f"Reprocesando pendiente "
            f"ID {id_error} - "
            f"Orden {orden}"
        ),
    )

    logger.info(
        (
            "Reprocesando pendiente "
            "ID %s - Orden %s"
        ),
        id_error,
        orden,
    )

    try:
        resultado = recibir_venta(
            payload
        )

        if resultado.get("status") in {
            "success",
            "duplicada",
        }:
            marcar_error_resuelto(
                id_error
            )

            registrar_evento(
                "INFO",
                (
                    f"Pendiente ID {id_error} "
                    "resuelto correctamente"
                ),
            )

            logger.info(
                (
                    "Pendiente ID %s "
                    "resuelto correctamente"
                ),
                id_error,
            )

    except Exception as error:
        registrar_evento(
            "ERROR",
            (
                "Falló el reproceso del pendiente "
                f"ID {id_error}"
            ),
        )

        logger.exception(
            (
                "Falló el reproceso del "
                "pendiente ID %s: %s"
            ),
            id_error,
            error,
        )

    return RedirectResponse(
        "/db/errores",
        status_code=303,
    )


# =====================================================
# CONSULTAR FACTURA EN ARCA
# =====================================================

@app.get("/consultar/{numero_factura}")
def consultar_factura(
    numero_factura: int,
):
    try:
        registrar_evento(
            "INFO",
            (
                "Consultando factura "
                f"{numero_factura} en ARCA"
            ),
        )

        logger.info(
            (
                "Consultando factura "
                "%s en ARCA"
            ),
            numero_factura,
        )

        resultado = (
            afip
            .ElectronicBilling
            .getVoucherInfo(
                numero_factura,
                PUNTO_VENTA,
                TIPO_COMPROBANTE,
            )
        )

        if not resultado:
            registrar_evento(
                "ERROR",
                (
                    f"Factura {numero_factura} "
                    "no encontrada en ARCA"
                ),
            )

            logger.warning(
                (
                    "Factura %s no encontrada "
                    "en ARCA"
                ),
                numero_factura,
            )

            return {
                "status": "no_encontrada",
                "mensaje": (
                    "No se encontró la factura "
                    f"{numero_factura} en ARCA"
                ),
            }

        registrar_evento(
            "INFO",
            (
                f"Factura {numero_factura} "
                "encontrada en ARCA"
            ),
        )

        return {
            "status": "encontrada",
            "factura": numero_factura,
            "punto_venta": PUNTO_VENTA,
            "tipo_comprobante": (
                TIPO_COMPROBANTE
            ),
            "datos_arca": resultado,
        }

    except Exception as error:
        registrar_evento(
            "ERROR",
            (
                "Error consultando factura "
                f"{numero_factura}"
            ),
        )

        logger.exception(
            (
                "Error consultando factura "
                "%s en ARCA: %s"
            ),
            numero_factura,
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo consultar la factura "
                "en ARCA. El error fue registrado."
            ),
        ) from error


# =====================================================
# VISUALIZAR SQLITE - FACTURAS
# =====================================================

@app.get(
    "/db/facturas",
    response_class=HTMLResponse,
)
def ver_facturas_db():
    facturas = ultimas_facturas(100)

    html = f"""
    <!DOCTYPE html>
    <html lang="es">

    {head_html("Base SQLite - Facturas")}

    <body>
        <div class="contenedor">
            <div class="card">
                <h1>🧾 Facturas guardadas en SQLite</h1>

                <p>
                    <a href="/">
                        ← Volver al Dashboard
                    </a>
                </p>

                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Orden</th>
                        <th>Cliente</th>
                        <th>Factura</th>
                        <th>Total</th>
                        <th>CAE</th>
                        <th>Estado</th>
                        <th>ARCA</th>
                    </tr>
    """

    for factura in facturas:
        numero_factura = factura[3]

        html += f"""
                    <tr>
                        <td>{escape(str(factura[0]))}</td>
                        <td>{escape(str(factura[1]))}</td>
                        <td>{escape(str(factura[2]))}</td>
                        <td>{numero_factura}</td>
                        <td>${escape(str(factura[4]))}</td>
                        <td>{escape(str(factura[5]))}</td>
                        <td>{escape(str(factura[6]))}</td>

                        <td>
                            <a
                                href="/consultar/{numero_factura}"
                                target="_blank"
                            >
                                Consultar
                            </a>
                        </td>
                    </tr>
        """

    html += """
                </table>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(html)


# =====================================================
# VISUALIZAR SQLITE - EVENTOS
# =====================================================

@app.get(
    "/db/eventos",
    response_class=HTMLResponse,
)
def ver_eventos_db():
    eventos = ultimos_eventos(100)

    html = f"""
    <!DOCTYPE html>
    <html lang="es">

    {head_html("Base SQLite - Eventos")}

    <body>
        <div class="contenedor">
            <div class="card">
                <h1>📄 Eventos guardados en SQLite</h1>

                <p>
                    <a href="/">
                        ← Volver al Dashboard
                    </a>
                </p>

                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Tipo</th>
                        <th>Mensaje</th>
                    </tr>
    """

    for evento in eventos:
        clase = (
            "tipo-error"
            if evento[1] == "ERROR"
            else "tipo-info"
        )

        html += f"""
                    <tr>
                        <td>{escape(str(evento[0]))}</td>

                        <td class="{clase}">
                            {escape(str(evento[1]))}
                        </td>

                        <td>
                            {escape(str(evento[2]))}
                        </td>
                    </tr>
        """

    html += """
                </table>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(html)


# =====================================================
# VISUALIZAR SQLITE - ERRORES
# =====================================================

@app.get(
    "/db/errores",
    response_class=HTMLResponse,
)
def ver_errores_facturacion():
    errores = (
        ultimos_errores_facturacion(
            100
        )
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="es">

    {head_html("Errores de Facturación")}

    <body>
        <div class="contenedor">
            <div class="card">
                <h1>
                    ⚠️ Errores y pendientes de facturación
                </h1>

                <p>
                    <a href="/">
                        ← Volver al Dashboard
                    </a>
                </p>

                <table>
                    <tr>
                        <th>ID</th>
                        <th>Fecha</th>
                        <th>Orden</th>
                        <th>Cliente</th>
                        <th>Total</th>
                        <th>Error</th>
                        <th>Estado</th>
                        <th>Acción</th>
                    </tr>
    """

    for error in errores:
        id_error = error[0]
        estado_error = str(error[6])

        if estado_error == "pendiente":
            accion = f"""
                <form
                    action="/reprocesar-pendiente/{id_error}"
                    method="post"
                >
                    <button
                        class="boton-mini"
                        type="submit"
                    >
                        Reprocesar
                    </button>
                </form>
            """

            clase_estado = (
                "estado-pendiente"
            )

        else:
            accion = "Resuelto"

            clase_estado = (
                "estado-resuelto"
            )

        html += f"""
                    <tr>
                        <td>{id_error}</td>
                        <td>{escape(str(error[1]))}</td>
                        <td>{escape(str(error[2]))}</td>
                        <td>{escape(str(error[3]))}</td>
                        <td>${escape(str(error[4]))}</td>
                        <td>{escape(str(error[5]))}</td>

                        <td class="{clase_estado}">
                            {escape(estado_error)}
                        </td>

                        <td>{accion}</td>
                    </tr>
        """

    html += """
                </table>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(html)


# =====================================================
# ESTADO DEL SISTEMA
# =====================================================

@app.get("/estado")
def estado():
    return {
        "aplicacion": APP_NAME,
        "servidor": "online",
        "sqlite": "ok",
        "modo_arca": (
            "produccion"
            if AFIP_PRODUCTION
            else "homologacion"
        ),
        "facturas": contar_facturas(),
        "errores": contar_errores(),
        "pendientes": contar_pendientes(),
        "ultima_factura": ultima_factura(),
        "punto_venta": PUNTO_VENTA,
        "tipo_comprobante": TIPO_COMPROBANTE,
        "carpeta_ventas": str(
            CARPETA_VENTAS
        ),
        "csv_disponibles": (
            listar_csv_ventas()
        ),
    }
