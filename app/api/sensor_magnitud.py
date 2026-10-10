"""Endpoints de ``sensor_magnitudes`` (solo lectura)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencias import IdSensorMagnitud, sensor_o_404
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_db
from app.models.sensor import Sensor
from app.schemas.sensor_magnitud import SensorMagnitudOut

router = APIRouter(tags=["Sensor-magnitudes"])


@router.get(
    "/sensores/{sensor_id}/magnitudes",
    response_model=list[SensorMagnitudOut],
    summary="Magnitudes, unidades y rangos de un sensor",
    responses={404: {"description": "No existe un sensor con ese id"}},
)
def listar_magnitudes_del_sensor(
    sensor: Sensor = Depends(sensor_o_404), db: Session = Depends(get_db)
):
    magnitudes = crud_sensor_magnitud.listar_por_sensor(db, sensor.id)
    return [SensorMagnitudOut.desde_orm(m) for m in magnitudes]


@router.get(
    "/sensor-magnitudes/{sensor_magnitud_id}",
    response_model=SensorMagnitudOut,
    summary="Consultar una relación sensor-magnitud por su ID",
    responses={404: {"description": "No existe esa relación sensor-magnitud"}},
)
def obtener_sensor_magnitud(sensor_magnitud_id: IdSensorMagnitud, db: Session = Depends(get_db)):
    magnitud = crud_sensor_magnitud.obtener(db, sensor_magnitud_id)
    if magnitud is None:
        raise HTTPException(
            status_code=404,
            detail=f"No existe una relación sensor-magnitud con id {sensor_magnitud_id}",
        )
    return SensorMagnitudOut.desde_orm(magnitud)
