"""Esquemas Pydantic de respuesta para ``sensores``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.tiempo import formatear_local
from app.models.sensor import Sensor


class SensorOut(BaseModel):
    id: int
    codigo: str = Field(description="Código del sensor; es el `sensor_id` del payload MQTT.")
    nombre: str
    categoria: str = Field(description="AIRE, GAS, AGUA o AMBIENTE.")
    ubicacion: str
    activo: bool
    fecha_registro_local: str = Field(
        description="Fecha de registro en hora de Colombia (UTC-05:00)."
    )

    @classmethod
    def desde_orm(cls, sensor: Sensor) -> "SensorOut":
        return cls(
            id=sensor.id,
            codigo=sensor.codigo,
            nombre=sensor.nombre,
            categoria=sensor.categoria,
            ubicacion=sensor.ubicacion,
            activo=sensor.activo,
            fecha_registro_local=formatear_local(sensor.fecha_registro),
        )
