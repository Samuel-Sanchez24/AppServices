"""Acceso a datos de ``sensor_magnitudes``. Solo lectura (catálogo del docente)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor_magnitud import SensorMagnitud


def obtener(db: Session, sensor_magnitud_id: int) -> SensorMagnitud | None:
    return db.get(SensorMagnitud, sensor_magnitud_id)


def listar_por_sensor(db: Session, sensor_id: int) -> list[SensorMagnitud]:
    consulta = (
        select(SensorMagnitud)
        .where(SensorMagnitud.sensor_id == sensor_id)
        .order_by(SensorMagnitud.id)
    )
    return list(db.scalars(consulta))


def obtener_por_sensor_y_magnitud(
    db: Session, sensor_id: int, magnitud: str
) -> SensorMagnitud | None:
    return db.scalar(
        select(SensorMagnitud).where(
            SensorMagnitud.sensor_id == sensor_id, SensorMagnitud.magnitud == magnitud
        )
    )
