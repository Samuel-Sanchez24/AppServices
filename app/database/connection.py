"""Conexión a PostgreSQL con SQLAlchemy (engine, sesiones y clase base ORM)."""

from __future__ import annotations

import ssl
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Clase base de todos los modelos ORM (``app/models``)."""


SEGUNDOS_ESPERA_CONEXION = 10  # tiempo máximo para abrir una conexión nueva

_engine: Engine | None = None
_fabrica_sesiones: sessionmaker[Session] | None = None


def _argumentos_de_conexion(driver: str, sslmode: str | None) -> dict[str, object]:
    """Argumentos para abrir conexiones: el nombre del tiempo de espera y del SSL depende del controlador."""
    if driver == "pg8000":
        argumentos: dict[str, object] = {"timeout": SEGUNDOS_ESPERA_CONEXION}
        if sslmode == "disable":
            argumentos["ssl_context"] = False
        elif sslmode == "require":
            # Cifra el canal sin validar el certificado (equivale a sslmode=require de libpq).
            contexto = ssl.create_default_context()
            contexto.check_hostname = False
            contexto.verify_mode = ssl.CERT_NONE
            argumentos["ssl_context"] = contexto
        return argumentos

    argumentos = {"connect_timeout": SEGUNDOS_ESPERA_CONEXION}  # psycopg / psycopg2
    if sslmode:
        argumentos["sslmode"] = sslmode
    return argumentos


def _crear_engine() -> Engine:
    settings = get_settings()
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite":  # solo para pruebas locales sin PostgreSQL
        opciones: dict = {"connect_args": {"check_same_thread": False}}
        if url.database in (None, "", ":memory:"):
            opciones["poolclass"] = StaticPool
        return create_engine(url, **opciones)
    if url.drivername in ("postgresql", "postgres"):  # DATABASE_URL sin controlador explícito
        url = url.set(drivername=f"postgresql+{settings.driver_bd.nombre}")
    driver = url.get_driver_name()
    opciones_dialecto: dict = {"client_encoding": "utf8"} if driver == "pg8000" else {}  # tildes y ñ
    return create_engine(
        url,
        pool_pre_ping=True,  # descarta conexiones caídas antes de usarlas
        pool_size=5,
        max_overflow=5,
        connect_args=_argumentos_de_conexion(driver, settings.db_sslmode),
        **opciones_dialecto,
    )


def get_engine() -> Engine:
    """Engine único de la aplicación (se crea la primera vez que se necesita)."""
    global _engine
    if _engine is None:
        _engine = _crear_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _fabrica_sesiones
    if _fabrica_sesiones is None:
        _fabrica_sesiones = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _fabrica_sesiones


def comprobar_conexion() -> None:
    """Ejecuta ``SELECT 1``; lanza la excepción de SQLAlchemy si la base no responde."""
    with get_engine().connect() as conexion:
        conexion.execute(text("SELECT 1"))


def configurar_engine(engine: Engine | None) -> None:
    """Reemplaza (o reinicia con ``None``) el engine. Útil en pruebas."""
    global _engine, _fabrica_sesiones
    _engine = engine
    _fabrica_sesiones = None


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por solicitud, cerrada al terminar."""
    sesion = get_session_factory()()
    try:
        yield sesion
    finally:
        sesion.close()
