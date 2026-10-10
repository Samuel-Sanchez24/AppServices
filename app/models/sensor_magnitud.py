"""Modelo ORM de la tabla ``sensor_magnitudes`` (magnitudes, unidades y rangos por sensor)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.medicion import Medicion
    from app.models.sensor import Sensor


class SensorMagnitud(Base):
    __tablename__ = "sensor_magnitudes"
    __table_args__ = (
        UniqueConstraint("sensor_id", "magnitud", name="uq_sensor_magnitudes_sensor_magnitud"),
        CheckConstraint("valor_minimo < valor_maximo", name="ck_sensor_magnitudes_rango"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # FK -> sensores(id)  (ON UPDATE CASCADE, ON DELETE RESTRICT)
    sensor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sensores.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    magnitud: Mapped[str] = mapped_column(String(50), nullable=False)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    valor_maximo: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # sensores 1:N sensor_magnitudes  y  sensor_magnitudes 1:N mediciones
    sensor: Mapped["Sensor"] = relationship(back_populates="magnitudes")
    mediciones: Mapped[list["Medicion"]] = relationship(back_populates="sensor_magnitud")
