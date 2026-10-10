"""Modelo ORM de la tabla ``mediciones`` (lo único que la aplicación escribe)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.sensor_magnitud import SensorMagnitud


class Medicion(Base):
    __tablename__ = "mediciones"
    __table_args__ = (
        Index("idx_mediciones_sensor_magnitud", "sensor_magnitud_id"),
        Index("idx_mediciones_timestamp_utc", "timestamp_utc"),
        Index("idx_mediciones_magnitud_timestamp", "sensor_magnitud_id", "timestamp_utc"),
    )

    # BIGSERIAL en PostgreSQL (la variante Integer solo existe para poder probar con SQLite).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    # FK -> sensor_magnitudes(id)  (ON UPDATE CASCADE, ON DELETE RESTRICT)
    sensor_magnitud_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sensor_magnitudes.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    # Instante de la medición, siempre en UTC.
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # La asigna la base de datos (DEFAULT NOW()) al insertar.
    fecha_recepcion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sensor_magnitud: Mapped["SensorMagnitud"] = relationship(back_populates="mediciones")
