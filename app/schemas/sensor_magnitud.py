"""Esquemas Pydantic de respuesta para ``sensor_magnitudes``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.sensor_magnitud import SensorMagnitud


class SensorMagnitudOut(BaseModel):
    id: int
    sensor_id: int
    magnitud: str = Field(description="Nombre de la magnitud tal como llega en el payload.")
    unidad: str
    valor_minimo: float
    valor_maximo: float

    @classmethod
    def desde_orm(cls, magnitud: SensorMagnitud) -> "SensorMagnitudOut":
        return cls(
            id=magnitud.id,
            sensor_id=magnitud.sensor_id,
            magnitud=magnitud.magnitud,
            unidad=magnitud.unidad,
            valor_minimo=float(magnitud.valor_minimo),
            valor_maximo=float(magnitud.valor_maximo),
        )
