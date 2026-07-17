from html import escape

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from app.logger import logger


def pagina_error(
    titulo: str,
    mensaje: str,
    codigo: int,
) -> HTMLResponse:
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        <title>{escape(titulo)}</title>

        <link
            rel="stylesheet"
            href="/static/css/style.css"
        >
    </head>

    <body>
        <div class="contenedor">
            <div class="card">
                <h1>{escape(titulo)}</h1>

                <p>
                    {escape(mensaje)}
                </p>

                <p>
                    Código de error: {codigo}
                </p>

                <a
                    class="boton-secundario"
                    href="/"
                >
                    Volver al inicio
                </a>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(
        content=html,
        status_code=codigo,
    )


async def manejar_error_404(
    request: Request,
    exc: Exception,
) -> HTMLResponse:
    logger.warning(
        "Ruta no encontrada: %s %s",
        request.method,
        request.url.path,
    )

    return pagina_error(
        titulo="Página no encontrada",
        mensaje=(
            "La dirección solicitada no existe "
            "o fue modificada."
        ),
        codigo=404,
    )


async def manejar_error_validacion(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "Datos inválidos en %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "mensaje": (
                "Los datos enviados son inválidos "
                "o están incompletos."
            ),
            "detalle": exc.errors(),
        },
    )


async def manejar_error_general(
    request: Request,
    exc: Exception,
) -> HTMLResponse:
    logger.exception(
        "Error interno en %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )

    return pagina_error(
        titulo="Error interno",
        mensaje=(
            "Ocurrió un problema inesperado. "
            "El detalle fue registrado para su revisión."
        ),
        codigo=500,
    )