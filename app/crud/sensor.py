"""Acceso a datos de ``sensores``. Solo lectura: el catálogo lo administra el docente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor import Sensor


def obtener(db: Session, sensor_id: int) -> Sensor | None:
    return db.get(Sensor, sensor_id)


def obtener_por_codigo(db: Session, codigo: str) -> Sensor | None:
    return db.scalar(select(Sensor).where(Sensor.codigo == codigo))


def listar(
    db: Session,
    *,
    categoria: str | None = None,
    activo: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Sensor]:
    consulta = select(Sensor).order_by(Sensor.id)
    if categoria is not None:
        consulta = consulta.where(Sensor.categoria == categoria)
    if activo is not None:
        consulta = consulta.where(Sensor.activo == activo)
    return list(db.scalars(consulta.offset(skip).limit(limit)))
