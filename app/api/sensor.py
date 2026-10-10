"""Endpoints de ``sensores`` (solo lectura)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencias import sensor_o_404
from app.crud import sensor as crud_sensor
from app.database.connection import get_db
from app.models.sensor import Sensor
from app.schemas.sensor import SensorOut

router = APIRouter(tags=["Sensores"])


@router.get("/sensores", response_model=list[SensorOut], summary="Listar sensores")
def listar_sensores(
    categoria: Literal["AIRE", "GAS", "AGUA", "AMBIENTE"] | None = Query(
        None, description="Filtra por categoría."
    ),
    activo: bool | None = Query(None, description="Filtra por estado del sensor."),
    skip: int = Query(0, ge=0, description="Registros a omitir."),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros."),
    db: Session = Depends(get_db),
):
    sensores = crud_sensor.listar(db, categoria=categoria, activo=activo, skip=skip, limit=limit)
    return [SensorOut.desde_orm(s) for s in sensores]


# Declarada antes que /sensores/{sensor_id} para que «por-codigo» nunca se confunda con un id.
@router.get(
    "/sensores/por-codigo/{codigo}",
    response_model=SensorOut,
    summary="Consultar un sensor por su código",
    responses={404: {"description": "No existe un sensor con ese código"}},
)
def obtener_sensor_por_codigo(codigo: str, db: Session = Depends(get_db)):
    sensor = crud_sensor.obtener_por_codigo(db, codigo)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"No existe un sensor con código '{codigo}'")
    return SensorOut.desde_orm(sensor)


@router.get(
    "/sensores/{sensor_id}",
    response_model=SensorOut,
    summary="Consultar un sensor por su ID",
    responses={404: {"description": "No existe un sensor con ese id"}},
)
def obtener_sensor(sensor: Sensor = Depends(sensor_o_404)):
    return SensorOut.desde_orm(sensor)
