"""Fixtures de pruebas.

Por defecto las pruebas usan SQLite en memoria (no tocan PostgreSQL ni el broker MQTT).
Para ejecutarlas contra un PostgreSQL local propio se puede definir ``TEST_DATABASE_URL``;
por seguridad el nombre de esa base **debe terminar en ``_test``**.
"""

from __future__ import annotations

import os

# Antes de importar la aplicación: sin consumidor MQTT real durante las pruebas.
os.environ["MQTT_ENABLED"] = "false"
os.environ.setdefault("MQTT_BROKER", "localhost")
os.environ.setdefault("MQTT_TOPIC", "iot/sensors/GAS-004/data")

import json  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import resolver_driver_bd  # noqa: E402
from app.database.connection import Base, configurar_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Medicion, Sensor, SensorMagnitud  # noqa: E402
from app.services.ingesta import procesar_mensaje  # noqa: E402

TOPICO = "iot/sensors/GAS-004/data"

# Catálogo de ejemplo (el real lo suministra el docente en PostgreSQL).
CATALOGO = [
    ("TEST-001", "Sensor de prueba", "AMBIENTE", "Laboratorio", True,
     [("temperature", "C", -40, 85), ("humidity", "%", 0, 100)]),
    ("GAS-004", "Sensor de gases 4", "GAS", "Planta baja", True,
     [("co2", "ppm", 0, 5000), ("co", "ppm", 0, 1000), ("ch4", "ppm", 0, 10000)]),
    ("AIRE-009", "Sensor de aire 9", "AIRE", "Bodega", False,
     [("pm25", "ug/m3", 0, 500)]),
    ("GAS-005", "Sensor de gases 5", "GAS", "Planta alta", True,
     [("o2", "%", 0, 25)]),
]


@pytest.fixture(scope="session")
def engine():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        motor = create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        if not (parsed.database or "").endswith("_test"):
            pytest.exit("TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test", 2)
        motor = create_engine(url, pool_pre_ping=True)

    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
    configurar_engine(motor)
    yield motor
    configurar_engine(None)
    motor.dispose()


@pytest.fixture(scope="session")
def fabrica(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def catalogo(engine, fabrica) -> None:
    with fabrica() as db:
        for codigo, nombre, categoria, ubicacion, activo, magnitudes in CATALOGO:
            sensor = Sensor(
                codigo=codigo, nombre=nombre, categoria=categoria, ubicacion=ubicacion, activo=activo
            )
            sensor.magnitudes = [
                SensorMagnitud(
                    magnitud=m, unidad=u, valor_minimo=Decimal(lo), valor_maximo=Decimal(hi)
                )
                for m, u, lo, hi in magnitudes
            ]
            db.add(sensor)
        db.commit()


@pytest.fixture(autouse=True)
def driver_bd_sin_cache() -> Iterator[None]:
    """La elección del controlador de PostgreSQL se guarda en caché: cada prueba parte de cero."""
    resolver_driver_bd.cache_clear()
    yield
    resolver_driver_bd.cache_clear()


@pytest.fixture(autouse=True)
def limpiar_mediciones(fabrica) -> Iterator[None]:
    yield
    with fabrica() as db:
        db.execute(delete(Medicion))
        db.commit()


@pytest.fixture
def db(fabrica) -> Iterator[Session]:
    with fabrica() as sesion:
        yield sesion


@pytest.fixture
def client(fabrica) -> Iterator[TestClient]:
    def _get_db() -> Iterator[Session]:
        with fabrica() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# -- utilidades usadas por varios archivos de prueba -----------------------------------
def payload(
    sensor_id: str = "GAS-004",
    timestamp: object = "2026-10-07T16:25:30Z",
    measurements: object = None,
) -> dict:
    if measurements is None:
        measurements = {"co2": {"value": 412.5, "unit": "ppm"}}
    return {"sensor_id": sensor_id, "timestamp": timestamp, "measurements": measurements}


def enviar(db: Session, mensaje: object, topico: str = TOPICO):
    """Pasa un mensaje por la misma función que usa el consumidor MQTT."""
    crudo = mensaje if isinstance(mensaje, (bytes, str)) else json.dumps(mensaje)
    return procesar_mensaje(db, topico, crudo)


def total_mediciones(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Medicion))


@pytest.fixture
def historico(db) -> int:
    """5 payloads de GAS-004 (3 magnitudes cada uno), uno por minuto desde 16:00:00Z."""
    for i in range(5):
        resultado = enviar(
            db,
            payload(
                timestamp=f"2026-10-07T16:0{i}:00Z",
                measurements={
                    "co2": {"value": 400 + i, "unit": "ppm"},
                    "co": {"value": i, "unit": "ppm"},
                    "ch4": {"value": 100 + i, "unit": "ppm"},
                },
            ),
        )
        assert resultado.almacenado, resultado.resumen()
    return 15  # filas almacenadas
