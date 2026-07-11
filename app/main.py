import datetime
import subprocess
import sys
import os
import time
from pathlib import Path
from html import escape

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from afip import Afip

from app.database import (
    inicializar,
    registrar_evento,
    ultimos_eventos,
    guardar_factura,
    contar_facturas,
    contar_errores,
    ultima_factura,
    ultimas_facturas,
    existe_orden_facturada,
    registrar_error_facturacion,
    ultimos_errores_facturacion,
    contar_pendientes,
    obtener_error_facturacion,
    marcar_error_resuelto
)

from app.logger import logger


app = FastAPI(title="Chuli Facturador")

app.mount("/static", StaticFiles(directory="static"), name="static")

inicializar()

logger.info("Servidor iniciado")
registrar_evento("INFO", "Servidor iniciado")


# =====================================================
# CARPETAS / ARCHIVOS
# =====================================================

LOG_PROCESO = Path("logs/ultimo_proceso.txt")
LOG_PROCESO.parent.mkdir(exist_ok=True)

CARPETA_VENTAS = Path("ventas")
CARPETA_VENTAS.mkdir(exist_ok=True)

FAVICON = "https://d22fxaf9t8d39k.cloudfront.net/1dfabd14f4725ee6bceb4fbfccfd8acfc2995aef483ad49a1407d95fc2d86d29140661.png"


def head_html(titulo="Chuli Facturador"):
    return f"""
    <head>
        <meta charset="UTF-8">
        <title>{titulo}</title>
        <link rel="shortcut icon" href="{FAVICON}" />
        <link rel="stylesheet" href="/static/css/style.css">
    </head>
    """


def leer_ultimo_proceso():
    if LOG_PROCESO.exists():
        return LOG_PROCESO.read_text(encoding="utf-8", errors="replace")
    return "Todavía no se ejecutó ningún proceso."


def guardar_ultimo_proceso(texto):
    LOG_PROCESO.write_text(texto, encoding="utf-8")


def listar_csv_ventas():
    archivos = []

    for archivo in CARPETA_VENTAS.glob("*.csv"):
        archivos.append(str(archivo).replace("\\", "/"))

    return sorted(archivos)


# =====================================================
# CONEXIÓN CON ARCA / AFIP SDK
# =====================================================

with open("certificado.crt", "r", encoding="utf-8") as archivo_cert:
    contenido_certificado = archivo_cert.read()

with open("privada.key", "r", encoding="utf-8") as archivo_key:
    contenido_llave = archivo_key.read()


afip = Afip({
    "CUIT": 20270875409,
    "cert": contenido_certificado,
    "key": contenido_llave,
    "production": False,
    "access_token": "pnGqioNL9IoYHRcD6qmGVbyLWfscrhWA877v3XYAWgva4yzcVjdgVRsSonTvitOZ"
})


# =====================================================
# REINTENTOS ARCA
# =====================================================

def es_error_temporal(error):
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
        "no disponible"
    ]

    for palabra in palabras_temporales:
        if palabra in mensaje:
            return True

    return False


def crear_voucher_con_reintentos(data_afip, id_orden, numero_factura, intentos=4):
    esperas = [5, 10, 20, 40]
    ultimo_error = None

    for intento in range(intentos):
        numero_intento = intento + 1

        try:
            registrar_evento(
                "INFO",
                f"Intento {numero_intento}/{intentos} - Solicitando CAE para orden {id_orden}, factura {numero_factura}"
            )

            resultado = afip.ElectronicBilling.createVoucher(data_afip)

            registrar_evento(
                "INFO",
                f"CAE obtenido en intento {numero_intento} - Orden {id_orden}"
            )

            return resultado

        except Exception as e:
            ultimo_error = e

            if es_error_temporal(e) and intento < intentos - 1:
                segundos = esperas[intento]

                registrar_evento(
                    "ERROR",
                    f"ARCA congestionado/temporal en orden {id_orden}. Reintentando en {segundos} segundos. Error: {str(e)}"
                )

                time.sleep(segundos)
                continue

            registrar_evento(
                "ERROR",
                f"No se pudo obtener CAE para orden {id_orden}. Error final: {str(e)}"
            )

            raise ultimo_error


# =====================================================
# DASHBOARD
# =====================================================

@app.get("/", response_class=HTMLResponse)
def dashboard():

    total_facturas = contar_facturas()
    total_errores = contar_errores()
    total_pendientes = contar_pendientes()
    ultima = ultima_factura()
    eventos = ultimos_eventos()
    facturas = ultimas_facturas()
    salida_proceso = escape(leer_ultimo_proceso())
    archivos_csv = listar_csv_ventas()

    opciones_csv = ""

    if archivos_csv:
        for archivo in archivos_csv:
            opciones_csv += f"""
                <option value="{archivo}">
                    {archivo}
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

    {head_html("Chuli Facturador")}

    <body>
        <div class="contenedor">

            <div class="header">
                <div>
                    <h1>🧾 Chuli Facturador</h1>
                    <p>Dashboard v0.1 - Homologación ARCA</p>
                </div>
            </div>

            <div class="grid">

                <div class="card">
                    <h3>Servidor</h3>
                    <div class="numero ok">ONLINE</div>
                </div>

                <div class="card">
                    <h3>SQLite</h3>
                    <div class="numero ok">OK</div>
                </div>

                <div class="card">
                    <h3>Facturas</h3>
                    <div class="numero">{total_facturas}</div>
                </div>

                <div class="card">
                    <h3>Errores</h3>
                    <div class="numero error">{total_errores}</div>
                </div>

                <div class="card">
                    <h3>Pendientes</h3>
                    <div class="numero error">{total_pendientes}</div>
                </div>

            </div>

            <div class="card">
                <h3>Última factura emitida</h3>
                <div class="numero">#{ultima}</div>

                <br>

                <a class="boton-secundario" href="/db/facturas">
                    Ver facturas SQLite
                </a>

                <a class="boton-secundario" href="/db/eventos">
                    Ver eventos SQLite
                </a>

                <a class="boton-secundario" href="/db/errores">
                    Ver pendientes
                </a>

                <br><br>

                <form action="/procesar" method="post">

                    <label><b>Seleccionar archivo CSV:</b></label>
                    <br><br>

                    <select name="archivo_csv">
                        {opciones_csv}
                    </select>

                    <br><br>

                    <button class="boton" type="submit">
                        ▶ Procesar lote seleccionado
                    </button>

                </form>

                <div class="aviso">
                    Los archivos CSV deben estar dentro de la carpeta <b>ventas/</b>.
                    Recomendado: <b>AAAA-MM-DD_a_AAAA-MM-DD.csv</b>
                </div>
            </div>

            <div class="card seccion">
                <h2>Consola del último proceso</h2>
                <div class="consola">{salida_proceso}</div>
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

    for f in facturas:
        numero_factura = f[3]

        html += f"""
                    <tr>
                        <td>{f[0]}</td>
                        <td>{f[1]}</td>
                        <td>{f[2]}</td>
                        <td>{numero_factura}</td>
                        <td>${f[4]}</td>
                        <td>{f[5]}</td>
                        <td>{f[6]}</td>
                        <td>
                            <a href="/consultar/{numero_factura}" target="_blank">
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

    for e in eventos:
        clase = "tipo-error" if e[1] == "ERROR" else "tipo-info"

        html += f"""
                    <tr>
                        <td>{e[0]}</td>
                        <td class="{clase}">{e[1]}</td>
                        <td>{e[2]}</td>
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
def procesar(archivo_csv: str = Form(...)):

    if not archivo_csv:
        mensaje = "No se seleccionó ningún archivo CSV."
        guardar_ultimo_proceso(mensaje)
        registrar_evento("ERROR", mensaje)
        return RedirectResponse("/", status_code=303)

    registrar_evento("INFO", f"Procesamiento iniciado desde Dashboard: {archivo_csv}")

    try:
        ruta = Path(archivo_csv)

        if not ruta.exists():
            mensaje = f"El archivo seleccionado no existe: {archivo_csv}"
            guardar_ultimo_proceso(mensaje)
            registrar_evento("ERROR", mensaje)
            return RedirectResponse("/", status_code=303)

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        resultado = subprocess.run(
            [sys.executable, "procesar_lote.py", archivo_csv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )

        salida = ""
        salida += "========== STDOUT ==========\n"
        salida += resultado.stdout or ""

        salida += "\n\n========== STDERR ==========\n"
        salida += resultado.stderr or ""

        salida += f"\n\n========== CÓDIGO DE SALIDA: {resultado.returncode} ==========\n"

        guardar_ultimo_proceso(salida)

        if resultado.returncode == 0:
            registrar_evento("INFO", f"Proceso finalizado correctamente: {archivo_csv}")
        else:
            registrar_evento("ERROR", f"El proceso terminó con error: {archivo_csv}")

    except Exception as e:
        mensaje = f"Error ejecutando procesar_lote.py: {str(e)}"
        guardar_ultimo_proceso(mensaje)
        registrar_evento("ERROR", mensaje)

    return RedirectResponse("/", status_code=303)


# =====================================================
# WEBHOOK QUE RECIBE LAS ÓRDENES Y FACTURA EN ARCA
# =====================================================

@app.post("/webhook-empretienda")
def recibir_venta(datos_venta: dict):

    try:
        id_orden = datos_venta["id_orden"]
        cliente = datos_venta["cliente"]["nombre"]
        total = datos_venta["total"]

        factura_existente = existe_orden_facturada(id_orden)

        if factura_existente:
            numero_factura_existente = factura_existente[1]
            cae_existente = factura_existente[2]

            registrar_evento(
                "INFO",
                f"Orden {id_orden} omitida: ya facturada como factura {numero_factura_existente}"
            )

            return {
                "status": "duplicada",
                "mensaje": "La orden ya fue facturada anteriormente",
                "orden": id_orden,
                "factura": numero_factura_existente,
                "CAE": cae_existente
            }

        registrar_evento(
            "INFO",
            f"Orden {id_orden} recibida - {cliente} - ${total}"
        )

        tipo_comprobante = 11
        punto_venta = 1

        ultimo_numero = afip.ElectronicBilling.getLastVoucher(
            punto_venta,
            tipo_comprobante
        )

        numero_nueva_factura = ultimo_numero + 1
        fecha_actual = datetime.datetime.now().strftime("%Y%m%d")

        tipo_doc_cliente = datos_venta["cliente"]["tipo_doc"]

        if tipo_doc_cliente == "DNI":
            doc_tipo_afip = 96
        elif tipo_doc_cliente == "CUIT":
            doc_tipo_afip = 80
        else:
            doc_tipo_afip = 99

        dni_cuit = datos_venta["cliente"]["dni_cuit"]

        if dni_cuit and dni_cuit.isdigit():
            doc_nro = int(dni_cuit)
        else:
            doc_nro = 0
            doc_tipo_afip = 99

        data_afip = {
            "CantReg": 1,
            "PtoVta": punto_venta,
            "CbteTipo": tipo_comprobante,
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
            "CondicionIVAReceptorId": datos_venta.get(
                "CondicionIVAReceptorId",
                5
            )
        }

        resultado = crear_voucher_con_reintentos(
            data_afip=data_afip,
            id_orden=id_orden,
            numero_factura=numero_nueva_factura,
            intentos=4
        )

        cae = resultado.get("CAE")

        vencimiento = (
            resultado.get("CAEFchVto")
            or resultado.get("CAEFAreaVenc")
            or resultado.get("Vencimiento")
            or ""
        )

        guardar_factura(
            orden=id_orden,
            cliente=cliente,
            numero_factura=numero_nueva_factura,
            total=total,
            cae=cae,
            vencimiento=vencimiento,
            estado="Emitida"
        )

        registrar_evento(
            "INFO",
            f"Factura {numero_nueva_factura} emitida correctamente - Orden {id_orden}"
        )

        return {
            "status": "success",
            "orden": id_orden,
            "factura": numero_nueva_factura,
            "CAE": cae,
            "Vencimiento": vencimiento,
            "respuesta_completa": resultado
        }

    except Exception as e:

        id_orden_error = datos_venta.get("id_orden", 0)
        cliente_error = datos_venta.get("cliente", {}).get("nombre", "Sin cliente")
        total_error = datos_venta.get("total", 0)

        registrar_evento(
            "ERROR",
            f"Error orden {id_orden_error}: {str(e)}"
        )

        registrar_error_facturacion(
            orden=id_orden_error,
            cliente=cliente_error,
            total=total_error,
            error=str(e),
            payload=datos_venta
        )

        raise HTTPException(
            status_code=500,
            detail=f"Error devuelto por ARCA: {str(e)}"
        )


# =====================================================
# REPROCESAR PENDIENTES
# =====================================================

@app.post("/reprocesar-pendiente/{id_error}")
def reprocesar_pendiente(id_error: int):

    error_guardado = obtener_error_facturacion(id_error)

    if not error_guardado:
        registrar_evento(
            "ERROR",
            f"No se encontró pendiente con ID {id_error}"
        )

        return RedirectResponse("/db/errores", status_code=303)

    if error_guardado["estado"] != "pendiente":
        registrar_evento(
            "INFO",
            f"Pendiente {id_error} ya no está pendiente"
        )

        return RedirectResponse("/db/errores", status_code=303)

    payload = error_guardado["payload"]
    orden = error_guardado["orden"]

    registrar_evento(
        "INFO",
        f"Reprocesando pendiente ID {id_error} - Orden {orden}"
    )

    try:
        resultado = recibir_venta(payload)

        if resultado.get("status") in ["success", "duplicada"]:
            marcar_error_resuelto(id_error)

            registrar_evento(
                "INFO",
                f"Pendiente ID {id_error} resuelto correctamente"
            )

    except Exception as e:
        registrar_evento(
            "ERROR",
            f"Falló reproceso pendiente ID {id_error}: {str(e)}"
        )

    return RedirectResponse("/db/errores", status_code=303)


# =====================================================
# CONSULTAR FACTURA EN ARCA
# =====================================================

@app.get("/consultar/{numero_factura}")
def consultar_factura(numero_factura: int):

    try:
        punto_venta = 1
        tipo_comprobante = 11

        registrar_evento(
            "INFO",
            f"Consultando factura {numero_factura} en ARCA"
        )

        resultado = afip.ElectronicBilling.getVoucherInfo(
            numero_factura,
            punto_venta,
            tipo_comprobante
        )

        if not resultado:
            registrar_evento(
                "ERROR",
                f"Factura {numero_factura} no encontrada en ARCA"
            )

            return {
                "status": "no_encontrada",
                "mensaje": f"No se encontró la factura {numero_factura} en ARCA"
            }

        registrar_evento(
            "INFO",
            f"Factura {numero_factura} encontrada en ARCA"
        )

        return {
            "status": "encontrada",
            "factura": numero_factura,
            "punto_venta": punto_venta,
            "tipo_comprobante": tipo_comprobante,
            "datos_arca": resultado
        }

    except Exception as e:

        registrar_evento(
            "ERROR",
            f"Error consultando factura {numero_factura}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Error consultando factura en ARCA: {str(e)}"
        )


# =====================================================
# VISUALIZAR SQLITE - FACTURAS
# =====================================================

@app.get("/db/facturas", response_class=HTMLResponse)
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
            <a href="/">← Volver al Dashboard</a>
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

    for f in facturas:
        numero_factura = f[3]

        html += f"""
            <tr>
                <td>{f[0]}</td>
                <td>{f[1]}</td>
                <td>{f[2]}</td>
                <td>{numero_factura}</td>
                <td>${f[4]}</td>
                <td>{f[5]}</td>
                <td>{f[6]}</td>
                <td>
                    <a href="/consultar/{numero_factura}" target="_blank">
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

@app.get("/db/eventos", response_class=HTMLResponse)
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
            <a href="/">← Volver al Dashboard</a>
        </p>

        <table>
            <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Mensaje</th>
            </tr>
    """

    for e in eventos:
        clase = "tipo-error" if e[1] == "ERROR" else "tipo-info"

        html += f"""
            <tr>
                <td>{e[0]}</td>
                <td class="{clase}">{e[1]}</td>
                <td>{e[2]}</td>
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
# VISUALIZAR SQLITE - ERRORES / PENDIENTES
# =====================================================

@app.get("/db/errores", response_class=HTMLResponse)
def ver_errores_facturacion():

    errores = ultimos_errores_facturacion(100)

    html = f"""
    <!DOCTYPE html>
    <html lang="es">

    {head_html("Errores de Facturación")}

    <body>

    <div class="contenedor">
    <div class="card">
        <h1>⚠️ Errores / pendientes de facturación</h1>

        <p>
            <a href="/">← Volver al Dashboard</a>
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

    for e in errores:
        id_error = e[0]
        estado = e[6]

        if estado == "pendiente":
            accion = f"""
                <form action="/reprocesar-pendiente/{id_error}" method="post">
                    <button class="boton-mini" type="submit">
                        Reprocesar
                    </button>
                </form>
            """
        else:
            accion = "Resuelto"

        clase_estado = "estado-pendiente" if estado == "pendiente" else "estado-resuelto"

        html += f"""
            <tr>
                <td>{e[0]}</td>
                <td>{e[1]}</td>
                <td>{e[2]}</td>
                <td>{e[3]}</td>
                <td>${e[4]}</td>
                <td>{e[5]}</td>
                <td class="{clase_estado}">{estado}</td>
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
# ESTADO SIMPLE DEL SISTEMA
# =====================================================

@app.get("/estado")
def estado():

    return {
        "servidor": "online",
        "sqlite": "ok",
        "facturas": contar_facturas(),
        "errores": contar_errores(),
        "pendientes": contar_pendientes(),
        "ultima_factura": ultima_factura(),
        "csv_disponibles": listar_csv_ventas()
    }