"""Dependencias y tipos reutilizables por los routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.crud import sensor as crud_sensor
from app.database.connection import get_db
from app.models.sensor import Sensor

# Los límites evitan que un id enorme provoque un error de desbordamiento en PostgreSQL
# (INTEGER = 32 bits, BIGINT = 64 bits). Cualquier otro entero no existente responde 404.
IdSensor = Annotated[
    int,
    Path(description="ID numérico (clave primaria) del sensor.", ge=-(2**31), le=2**31 - 1),
]
IdSensorMagnitud = Annotated[
    int,
    Path(description="ID numérico de la relación sensor-magnitud.", ge=-(2**31), le=2**31 - 1),
]
IdMedicion = Annotated[
    int,
    Path(description="ID numérico (BIGINT) de la medición.", ge=-(2**63), le=2**63 - 1),
]


def sensor_o_404(sensor_id: IdSensor, db: Session = Depends(get_db)) -> Sensor:
    """Resuelve el sensor de la ruta o responde 404 si no existe."""
    sensor = crud_sensor.obtener(db, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"No existe un sensor con id {sensor_id}")
    return sensor
