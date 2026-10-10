"""Modelos ORM. Se importan todos aquí para que SQLAlchemy resuelva las relaciones."""

from app.models.medicion import Medicion
from app.models.sensor import Sensor
from app.models.sensor_magnitud import SensorMagnitud

__all__ = ["Medicion", "Sensor", "SensorMagnitud"]
