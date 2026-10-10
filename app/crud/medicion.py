"""Acceso a datos de ``mediciones``: crear (desde MQTT) y consultar (desde la API).

No hay actualización ni borrado: el histórico es de solo-inserción.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, contains_eager

from app.models.medicion import Medicion
from app.models.sensor import Sensor
from app.models.sensor_magnitud import SensorMagnitud


def crear_varias(
    db: Session,
    valores: Sequence[tuple[int, Decimal]],
    timestamp_utc: datetime,
) -> list[Medicion]:
    """Inserta una medición por magnitud (``sensor_magnitud_id``, ``valor``).

    Todas comparten el mismo ``timestamp_utc`` y se guardan en **una sola transacción**:
    o se almacenan todas o ninguna.
    """
    mediciones = [
        Medicion(sensor_magnitud_id=sensor_magnitud_id, valor=valor, timestamp_utc=timestamp_utc)
        for sensor_magnitud_id, valor in valores
    ]
    try:
        db.add_all(mediciones)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return mediciones


def _con_relaciones():
    """Consulta base que trae medición + magnitud + sensor en un solo SELECT."""
    return (
        select(Medicion)
        .join(Medicion.sensor_magnitud)
        .join(SensorMagnitud.sensor)
        .options(contains_eager(Medicion.sensor_magnitud).contains_eager(SensorMagnitud.sensor))
    )


def obtener(db: Session, medicion_id: int) -> Medicion | None:
    return db.scalar(_con_relaciones().where(Medicion.id == medicion_id))


def listar_por_sensor(
    db: Session,
    sensor_id: int,
    *,
    magnitud: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limit: int | None = None,
    ascendente: bool = False,
) -> list[Medicion]:
    """Histórico de un sensor con filtros combinables.

    ``limit`` devuelve las **últimas N** mediciones (las más recientes). El resultado se
    entrega de la más reciente a la más antigua, o al revés si ``ascendente=True``.
    """
    consulta = _con_relaciones().where(Sensor.id == sensor_id)
    if magnitud is not None:
        consulta = consulta.where(SensorMagnitud.magnitud == magnitud)
    if desde is not None:
        consulta = consulta.where(Medicion.timestamp_utc >= desde)
    if hasta is not None:
        consulta = consulta.where(Medicion.timestamp_utc <= hasta)

    consulta = consulta.order_by(Medicion.timestamp_utc.desc(), Medicion.id.desc())
    if limit is not None:
        consulta = consulta.limit(limit)

    filas = list(db.scalars(consulta).unique())
    if ascendente:
        filas.reverse()
    return filas


def ultima_por_sensor(
    db: Session, sensor_id: int, *, magnitud: str | None = None
) -> Medicion | None:
    """Medición más reciente del sensor (opcionalmente de una sola magnitud)."""
    filas = listar_por_sensor(db, sensor_id, magnitud=magnitud, limit=1)
    return filas[0] if filas else None
