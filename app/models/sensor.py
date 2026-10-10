"""Modelo ORM de la tabla ``sensores`` (catálogo suministrado por el docente)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.sensor_magnitud import SensorMagnitud


class Sensor(Base):
    __tablename__ = "sensores"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('AIRE', 'GAS', 'AGUA', 'AMBIENTE')", name="ck_sensores_categoria"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ``codigo`` es el ``sensor_id`` que llega en el payload MQTT (no es la PK numérica).
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # sensores 1:N sensor_magnitudes
    magnitudes: Mapped[list["SensorMagnitud"]] = relationship(
        back_populates="sensor", order_by="SensorMagnitud.id"
    )
