from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import medicion, salud, sensor, sensor_magnitud
from app.core.config import get_settings
from app.core.logging_config import configurar_logging
from app.database.connection import comprobar_conexion
from app.database.errores import describir_error, es_error_de_conexion
from app.mqtt.client import ClienteMQTT

logger = logging.getLogger("app.main")


def _verificar_base_de_datos() -> None:
    try:
        comprobar_conexion()
        logger.info("Conexión a PostgreSQL verificada")
    except Exception as exc:  # noqa: BLE001 - la API arranca igual; /salud informa el estado
        logger.error("No se pudo conectar a PostgreSQL: %s", exc.__class__.__name__)
        logger.debug("Detalle del error de conexión: %s", describir_error(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configurar_logging(settings.log_level)
    logger.info("Iniciando aplicación | configuración=%s", settings.resumen())
    _verificar_base_de_datos()

    cliente: ClienteMQTT | None = None
    if settings.mqtt_enabled:
        cliente = ClienteMQTT(settings)
        cliente.iniciar()
    else:
        logger.info("Consumidor MQTT deshabilitado (MQTT_ENABLED=false)")
    app.state.mqtt = cliente

    try:
        yield
    finally:
        if cliente is not None:
            cliente.detener()
        logger.info("Aplicación detenida")


app = FastAPI(
    title="API IoT — Taller 2",
    description=(
        "Adquisición de datos de un sensor IoT por **MQTT**, validación con **Pydantic**, "
        "persistencia en **PostgreSQL** mediante **SQLAlchemy ORM** y consulta por HTTP.\n\n"
        "Los datos se almacenan en UTC; las fechas de las respuestas se muestran en "
        "**hora de Colombia (UTC-05:00)**."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(sensor.router)
app.include_router(sensor_magnitud.router)
app.include_router(medicion.router)
app.include_router(salud.router)


@app.exception_handler(SQLAlchemyError)
async def manejar_error_de_base_de_datos(request: Request, exc: SQLAlchemyError):
    logger.error("Error de base de datos en %s: %s", request.url.path, exc.__class__.__name__)
    estado = 503 if es_error_de_conexion(exc) else 500
    return JSONResponse(
        status_code=estado, content={"detail": "Error al acceder a la base de datos"}
    )
