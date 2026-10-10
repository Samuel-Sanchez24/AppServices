"""Endpoints de ``mediciones`` (solo lectura; las inserciones llegan únicamente por MQTT)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.api.dependencias import IdMedicion, sensor_o_404
from app.core.tiempo import parsear_filtro_fecha
from app.crud import medicion as crud_medicion
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_db
from app.models.sensor import Sensor
from app.schemas.medicion import MedicionOut

router = APIRouter(tags=["Mediciones"])

_AYUDA_FECHA = (
    "Fecha ISO 8601. Con zona (`2026-10-07T16:00:00Z`, `2026-10-07T11:00:00-05:00`) se respeta; "
    "sin zona se interpreta como hora de Colombia; solo fecha (`2026-10-07`) abarca el día "
    "completo. Si usa `+hh:mm` codifíquelo como `%2B`."
)


def _fecha_o_422(nombre: str, valor: str | None, *, fin_de_dia: bool) -> datetime | None:
    """Convierte ``desde``/``hasta`` a UTC o responde 422 con el formato estándar de FastAPI."""
    if valor is None:
        return None
    try:
        return parsear_filtro_fecha(valor, fin_de_dia=fin_de_dia)
    except ValueError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", nombre),
                    "msg": f"Valor inválido para '{nombre}': {exc}",
                    "input": valor,
                }
            ]
        ) from exc


@router.get(
    "/mediciones/{medicion_id}",
    response_model=MedicionOut,
    summary="Consultar una medición por su ID",
    responses={404: {"description": "No existe una medición con ese id"}},
)
def obtener_medicion(medicion_id: IdMedicion, db: Session = Depends(get_db)):
    medicion = crud_medicion.obtener(db, medicion_id)
    if medicion is None:
        raise HTTPException(status_code=404, detail=f"No existe una medición con id {medicion_id}")
    return MedicionOut.desde_orm(medicion)


@router.get(
    "/sensores/{sensor_id}/mediciones",
    response_model=list[MedicionOut],
    summary="Histórico de mediciones de un sensor (filtros combinables)",
    responses={
        400: {"description": "`desde` es posterior a `hasta`"},
        404: {"description": "El sensor no existe o no tiene la magnitud indicada"},
        422: {"description": "Parámetro con tipo o formato inválido"},
    },
)
def listar_mediciones_del_sensor(
    sensor: Sensor = Depends(sensor_o_404),
    magnitud: str | None = Query(
        None, max_length=50, description="Filtra por magnitud, p. ej. `temperature`."
    ),
    desde: str | None = Query(None, description="Límite inferior (inclusive). " + _AYUDA_FECHA),
    hasta: str | None = Query(None, description="Límite superior (inclusive). " + _AYUDA_FECHA),
    limit: int | None = Query(
        None, ge=1, le=10000, description="Devuelve solo las últimas N mediciones."
    ),
    orden: Literal["asc", "desc"] = Query(
        "desc", description="`desc`: la más reciente primero; `asc`: la más antigua primero."
    ),
    db: Session = Depends(get_db),
):
    desde_utc = _fecha_o_422("desde", desde, fin_de_dia=False)
    hasta_utc = _fecha_o_422("hasta", hasta, fin_de_dia=True)
    if desde_utc is not None and hasta_utc is not None and desde_utc > hasta_utc:
        raise HTTPException(
            status_code=400, detail="El parámetro 'desde' no puede ser posterior a 'hasta'"
        )

    if magnitud is not None and (
        crud_sensor_magnitud.obtener_por_sensor_y_magnitud(db, sensor.id, magnitud) is None
    ):
        raise HTTPException(
            status_code=404,
            detail=f"El sensor '{sensor.codigo}' no tiene la magnitud '{magnitud}'",
        )

    mediciones = crud_medicion.listar_por_sensor(
        db,
        sensor.id,
        magnitud=magnitud,
        desde=desde_utc,
        hasta=hasta_utc,
        limit=limit,
        ascendente=(orden == "asc"),
    )
    return [MedicionOut.desde_orm(m) for m in mediciones]


@router.get(
    "/sensores/{sensor_id}/ultima-medicion",
    response_model=MedicionOut,
    summary="Medición más reciente de un sensor",
    responses={404: {"description": "El sensor no existe, no tiene mediciones o no tiene la magnitud"}},
)
def obtener_ultima_medicion(
    sensor: Sensor = Depends(sensor_o_404),
    magnitud: str | None = Query(
        None, max_length=50, description="Si se indica, devuelve la última de esa magnitud."
    ),
    db: Session = Depends(get_db),
):
    if magnitud is not None and (
        crud_sensor_magnitud.obtener_por_sensor_y_magnitud(db, sensor.id, magnitud) is None
    ):
        raise HTTPException(
            status_code=404,
            detail=f"El sensor '{sensor.codigo}' no tiene la magnitud '{magnitud}'",
        )

    medicion = crud_medicion.ultima_por_sensor(db, sensor.id, magnitud=magnitud)
    if medicion is None:
        raise HTTPException(
            status_code=404, detail=f"El sensor '{sensor.codigo}' aún no tiene mediciones"
        )
    return MedicionOut.desde_orm(medicion)
