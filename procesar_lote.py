import pandas as pd
import re
import requests
import sys
from pathlib import Path

from app.database import registrar_evento

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==========================================
# Configuración
# ==========================================

if len(sys.argv) > 1:
    archivo_csv = sys.argv[1]
else:
    archivo_csv = "ventasprueba.csv"

url_servidor = "http://127.0.0.1:8000/webhook-empretienda"


# ==========================================
# Carga robusta del CSV
# ==========================================

def cargar_csv(ruta_csv):
    """
    Intenta leer CSV exportados desde tienda online/Excel.
    Soporta separador coma, punto y coma, tabulador y distintos encodings.
    """

    encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252"]
    separadores = [None, ";", ",", "\t"]

    ultimo_error = None

    for encoding in encodings:
        for sep in separadores:
            try:
                df = pd.read_csv(
                    ruta_csv,
                    sep=sep,
                    engine="python",
                    encoding=encoding,
                    dtype=str,
                    quotechar='"',
                    on_bad_lines="error"
                )

                df.columns = [
                    str(col).replace("\ufeff", "").strip()
                    for col in df.columns
                ]

                return df

            except Exception as e:
                ultimo_error = e

    raise Exception(f"No se pudo leer el CSV. Último error: {ultimo_error}")


def validar_columnas(df):
    columnas_necesarias = [
        "#",
        "Fecha",
        "Facturada",
        "Cliente",
        "Email",
        "Teléfono",
        "Fact - Razón social",
        "Fact - Tipo de documento",
        "Fact - Número de documento",
        "Productos",
        "Total (sin envío)",
        "Costo de envío",
        "Método de pago"
    ]

    faltantes = []

    for columna in columnas_necesarias:
        if columna not in df.columns:
            faltantes.append(columna)

    if faltantes:
        raise Exception(
            "Faltan columnas en el CSV: "
            + ", ".join(faltantes)
            + f". Columnas encontradas: {list(df.columns)}"
        )


# ==========================================
# Funciones auxiliares
# ==========================================

def mapear_productos(texto_productos):
    lista_items = []

    if pd.isna(texto_productos):
        return lista_items

    lineas = str(texto_productos).split("\n")

    for linea in lineas:
        linea = linea.strip()

        if not linea:
            continue

        match = re.match(r"(\d+)x\s*(.*)", linea)

        if match:
            cantidad = int(match.group(1))
            descripcion = match.group(2)

            lista_items.append({
                "cantidad": cantidad,
                "descripcion": descripcion
            })

    return lista_items


def limpiar_numero(valor):
    if pd.isna(valor) or str(valor).strip() == "":
        return 0.0

    try:
        texto = str(valor).strip()

        # Si viene tipo 89.250,00
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")

        # Si viene tipo 89250,00
        elif "," in texto:
            texto = texto.replace(",", ".")

        return float(texto)

    except Exception:
        return 0.0


def valor_columna(fila, columna, defecto=""):
    valor = fila.get(columna, defecto)

    if pd.isna(valor):
        return defecto

    return str(valor).strip()


# ==========================================
# Inicio
# ==========================================

print("==================================================")
print("[INFO] INICIANDO PROCESAMIENTO DE VENTAS")
print("==================================================")
print(f"[INFO] Archivo seleccionado: {archivo_csv}")

registrar_evento(
    "INFO",
    f"Inicio procesamiento archivo {archivo_csv}"
)


# ==========================================
# Cargar CSV
# ==========================================

try:
    df = cargar_csv(archivo_csv)

    validar_columnas(df)

    mensaje = f"Archivo cargado correctamente. {len(df)} ventas encontradas."

    print(f"[OK] {mensaje}")
    print(f"[INFO] Columnas detectadas: {list(df.columns)}")
    print()

    registrar_evento("INFO", mensaje)

except Exception as e:
    print(f"[ERROR] Error al cargar el archivo CSV: {e}")

    registrar_evento(
        "ERROR",
        f"Error al cargar CSV {archivo_csv}: {e}"
    )

    exit(1)


# ==========================================
# Procesamiento
# ==========================================

procesadas = 0
ok = 0
errores = 0
omitidas = 0

for index, fila in df.iterrows():

    try:
        id_orden = int(str(fila["#"]).strip())
    except Exception:
        print(f"[WARN] Fila {index + 1} sin número de orden válido. Se omite.")
        registrar_evento(
            "ERROR",
            f"Fila {index + 1} sin número de orden válido"
        )
        errores += 1
        continue

    facturada = valor_columna(fila, "Facturada").lower()

    if facturada in ["si", "sí", "s", "yes", "true"]:
        print(f"[WARN] Orden #{id_orden} ya estaba facturada en el CSV.")

        registrar_evento(
            "INFO",
            f"Orden {id_orden} omitida por CSV: ya figuraba facturada"
        )

        omitidas += 1
        print("-" * 50)
        continue

    cliente = valor_columna(fila, "Cliente")
    email = valor_columna(fila, "Email")
    telefono = valor_columna(fila, "Teléfono")

    razon_social = valor_columna(
        fila,
        "Fact - Razón social",
        cliente
    )

    tipo_doc = valor_columna(
        fila,
        "Fact - Tipo de documento",
        "DNI"
    )

    numero_doc = valor_columna(
        fila,
        "Fact - Número de documento",
        ""
    )

    if numero_doc.endswith(".0"):
        numero_doc = numero_doc.replace(".0", "")

    datos_factura = {
        "id_orden": id_orden,
        "fecha": valor_columna(fila, "Fecha"),
        "total": limpiar_numero(fila["Total (sin envío)"]),
        "costo_envio": limpiar_numero(fila["Costo de envío"]),
        "cliente": {
            "nombre": cliente,
            "email": email,
            "telefono": telefono,
            "razon_social_fact": razon_social,
            "tipo_doc": tipo_doc,
            "dni_cuit": numero_doc
        },
        "items": mapear_productos(fila["Productos"]),
        "metodo_pago": valor_columna(fila, "Método de pago"),
        "CondicionIVAReceptorId": 5
    }

    print(
        f"[INFO] Enviando Orden #{id_orden} "
        f"({datos_factura['cliente']['nombre']}) - Total: ${datos_factura['total']}"
    )

    procesadas += 1

    try:
        respuesta = requests.post(
            url_servidor,
            json=datos_factura
        )

        if respuesta.status_code == 200:
            respuesta_json = respuesta.json()
            status = respuesta_json.get("status")

            if status == "duplicada":
                print(f"[WARN] Orden #{id_orden} ya estaba facturada en SQLite.")

                registrar_evento(
                    "INFO",
                    f"Orden {id_orden} omitida: ya estaba facturada en SQLite"
                )

                omitidas += 1

            else:
                print(f"[OK] Orden #{id_orden} procesada correctamente.")

                registrar_evento(
                    "INFO",
                    f"Orden {id_orden} procesada correctamente"
                )

                ok += 1

        else:
            print(f"[ERROR] Error Orden #{id_orden}: {respuesta.status_code}")
            print(respuesta.text)

            registrar_evento(
                "ERROR",
                f"Orden {id_orden}: {respuesta.text}"
            )

            errores += 1

    except Exception as e:
        print(f"[ERROR] Error de conexión: {e}")

        registrar_evento(
            "ERROR",
            f"Conexión: {e}"
        )

        errores += 1
        break

    print("-" * 50)


# ==========================================
# Resumen final
# ==========================================

print()
print("[FIN] PROCESO FINALIZADO")
print()
print(f"Archivo       : {archivo_csv}")
print(f"Ventas leídas : {len(df)}")
print(f"Procesadas    : {procesadas}")
print(f"Correctas     : {ok}")
print(f"Errores       : {errores}")
print(f"Omitidas      : {omitidas}")

registrar_evento(
    "INFO",
    f"Proceso finalizado archivo {archivo_csv}. OK:{ok} Error:{errores} Omitidas:{omitidas}"
)