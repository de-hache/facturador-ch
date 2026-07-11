# Chuli Facturador

Sistema MVP para procesar ventas por lote CSV y generar facturas electrónicas mediante ARCA/AFIP Web Service en modo homologación.

## Funcionalidades actuales

- Dashboard web con FastAPI
- Procesamiento de lotes CSV
- Emisión de Factura C en homologación
- Registro de facturas en SQLite
- Registro de eventos y errores
- Reintentos automáticos ante errores temporales de ARCA
- Control de duplicados por número de orden
- Consulta de comprobantes emitidos
- Pendientes de facturación
- Reproceso manual de pendientes
- CSS separado en archivo estático

## Estructura del proyecto

```text
app/
  main.py
  database.py
  logger.py

static/
  css/
    style.css

ventas/
  archivos CSV de ventas

data/
  base SQLite local

logs/
  archivos de logs

procesar_lote.py
requirements.txt
.gitignore
README.md