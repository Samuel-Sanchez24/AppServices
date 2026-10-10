"""Esquemas Pydantic de ``mediciones``.

* ``MedicionMQTT`` / ``MagnitudMQTT``: estructura esperada del payload JSON que publica el
  sensor (entrada). Validan campos obligatorios, tipos de datos y formato del timestamp.
* ``MedicionOut``: respuesta de la API (salida), con la fecha en hora de Colombia.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.core.tiempo import formatear_local, parsear_timestamp_mqtt
from app.models.medicion import Medicion


def _validar_timestamp(valor: object) -> datetime:
    if not isinstance(valor, str):
        raise ValueError("el timestamp debe ser texto ISO 8601, por ejemplo 2026-10-07T16:25:30Z")
    return parsear_timestamp_mqtt(valor)  # un ValueError aquí se reporta como error de validación


# Timestamp ISO 8601 con zona; una vez validado queda como datetime en UTC.
TimestampUTC = Annotated[datetime, BeforeValidator(_validar_timestamp)]


class MagnitudMQTT(BaseModel):
    """Una magnitud dentro de ``measurements``: ``{"value": 24.6, "unit": "C"}``."""

    model_config = ConfigDict(strict=True, extra="ignore")

    value: float = Field(allow_inf_nan=False)
    unit: str


class MedicionMQTT(BaseModel):
    """Payload completo publicado por el sensor."""

    model_config = ConfigDict(strict=True, extra="ignore")

    sensor_id: str
    timestamp: TimestampUTC
    measurements: dict[str, MagnitudMQTT] = Field(min_length=1)


class MedicionOut(BaseModel):
    id: int
    sensor_id: int
    sensor_codigo: str
    sensor_magnitud_id: int
    magnitud: str
    unidad: str
    valor: float
    timestamp_local: str = Field(
        description="Instante de la medición en hora de Colombia (UTC-05:00); se almacena en UTC."
    )
    fecha_recepcion_local: str = Field(
        description="Momento en que la aplicación almacenó la medición, en hora de Colombia."
    )

    @classmethod
    def desde_orm(cls, medicion: Medicion) -> "MedicionOut":
        magnitud = medicion.sensor_magnitud
        sensor = magnitud.sensor
        return cls(
            id=medicion.id,
            sensor_id=sensor.id,
            sensor_codigo=sensor.codigo,
            sensor_magnitud_id=magnitud.id,
            magnitud=magnitud.magnitud,
            unidad=magnitud.unidad,
            valor=float(medicion.valor),
            timestamp_local=formatear_local(medicion.timestamp_utc),
            fecha_recepcion_local=formatear_local(medicion.fecha_recepcion),
        )
