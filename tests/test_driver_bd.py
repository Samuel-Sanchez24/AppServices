"""Controlador de PostgreSQL (psycopg o pg8000) y errores de la base independientes del controlador.

No necesitan red ni servidor: ``pg8000`` se simula con un módulo mínimo, y el bloqueo de ``psycopg``
(DLL bloqueada por una directiva de «Control de aplicaciones» de Windows) con ``sys.modules``.
"""

from __future__ import annotations

import ssl
import sys
import types

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError

from app.core import config
from app.core.config import (
    ConfiguracionError,
    DriverBD,
    Settings,
    get_settings,
    resolver_driver_bd,
)
from app.database import connection
from app.database.connection import get_db
from app.database.errores import (
    codigo_sqlstate,
    describir_error,
    es_error_de_conexion,
    pista_error_bd,
)
from app.main import app

BLOQUEO_WINDOWS = (
    "ImportError: no pq wrapper available. Attempts made: - couldn't import psycopg 'binary' "
    "implementation: DLL load failed while importing pq: Una directiva de Control de aplicaciones "
    "bloqueó este archivo."
)


@pytest.fixture(autouse=True)
def ajustes_sin_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def configuracion(**cambios) -> Settings:
    base = dict(
        db_host="servidor.ejemplo", db_port=3002, db_name="appdb", db_user="postgres",
        db_password="p@ss:w/rd", database_url_env=None, mqtt_enabled=False, mqtt_broker=None,
        mqtt_port=1883, mqtt_topic=None, mqtt_username=None, mqtt_password=None,
        mqtt_keepalive=60, log_level="INFO", tolerancia_futuro_segundos=600,
    )
    base.update(cambios)
    return Settings(**base)


def error_servidor(clase, sqlstate: str, mensaje: str):
    """Error como lo entrega SQLAlchemy con pg8000: el servidor llega como diccionario en args[0]."""
    return clase("SELECT 1", {}, Exception({"S": "ERROR", "C": sqlstate, "M": mensaje}))


def pg8000_falso(monkeypatch, intentos: list[dict]) -> types.ModuleType:
    """Módulo mínimo con la forma de pg8000 que usa el dialecto de SQLAlchemy."""
    modulo = types.ModuleType("pg8000")
    modulo.__version__ = "1.31.5"
    modulo.paramstyle = "format"

    class Error(Exception):
        pass

    class InterfaceError(Error):
        pass

    def connect(*args, **kwargs):
        intentos.append(kwargs)
        raise InterfaceError("Can't create a connection to host servidor.ejemplo and port 3002")

    modulo.Error, modulo.InterfaceError, modulo.connect = Error, InterfaceError, connect
    monkeypatch.setitem(sys.modules, "pg8000", modulo)
    return modulo


# -- elección del controlador --------------------------------------------------------------
def test_auto_usa_psycopg_si_se_puede_cargar(monkeypatch):
    monkeypatch.setattr(config, "_motivo_no_disponible", lambda nombre: None)
    assert resolver_driver_bd("auto") == DriverBD("psycopg")


def test_auto_usa_pg8000_si_psycopg_esta_bloqueado(monkeypatch, caplog):
    monkeypatch.setattr(
        config, "_motivo_no_disponible", lambda n: BLOQUEO_WINDOWS if n == "psycopg" else None
    )
    with caplog.at_level("WARNING", logger="app.config"):
        driver = resolver_driver_bd("auto")
    assert driver.nombre == "pg8000"
    assert driver.descartados == (("psycopg", BLOQUEO_WINDOWS),)
    assert "psycopg no disponible" in driver.descripcion()
    assert "pg8000" in caplog.text


def test_driver_explicito_no_cambia_de_controlador(monkeypatch):
    monkeypatch.setattr(
        config, "_motivo_no_disponible", lambda n: "ImportError: bloqueado" if n == "psycopg" else None
    )
    with pytest.raises(ConfiguracionError, match="psycopg"):
        resolver_driver_bd("psycopg")
    assert resolver_driver_bd("pg8000") == DriverBD("pg8000")


def test_sin_ningun_controlador_el_error_explica_que_hacer(monkeypatch):
    monkeypatch.setattr(config, "_motivo_no_disponible", lambda n: f"ImportError: falta {n}")
    with pytest.raises(ConfiguracionError) as error:
        resolver_driver_bd("auto")
    texto = str(error.value)
    assert "psycopg" in texto and "pg8000" in texto and "pip install -r requirements.txt" in texto


def test_driver_desconocido_se_rechaza():
    with pytest.raises(ConfiguracionError):
        resolver_driver_bd("mysql")


def test_import_fallido_se_detecta_y_se_resume_en_una_linea(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)  # «import psycopg» lanza ImportError
    assert "psycopg" in config._motivo_no_disponible("psycopg")

    monkeypatch.setitem(sys.modules, "pg8000", types.ModuleType("pg8000"))
    assert config._motivo_no_disponible("pg8000") is None

    def import_bloqueado(nombre):
        raise ImportError("no pq wrapper available.\nAttempts made:\n  - DLL bloqueada")

    with monkeypatch.context() as parche:
        parche.setattr(config.importlib, "import_module", import_bloqueado)
        motivo = config._motivo_no_disponible("psycopg")
    assert motivo == "ImportError: no pq wrapper available. Attempts made: - DLL bloqueada"


# -- configuración -------------------------------------------------------------------------
@pytest.mark.parametrize("driver", ["psycopg", "pg8000"])
def test_la_url_usa_el_controlador_elegido(monkeypatch, driver):
    monkeypatch.setattr(config, "_motivo_no_disponible", lambda nombre: None)
    url = configuracion(db_driver=driver).database_url
    assert url.drivername == f"postgresql+{driver}"
    assert (url.host, url.port, url.database, url.username) == ("servidor.ejemplo", 3002, "appdb", "postgres")
    # la contraseña con caracteres especiales sobrevive al viaje por texto
    assert make_url(url.render_as_string(hide_password=False)).password == "p@ss:w/rd"


def test_variables_de_entorno_del_controlador(monkeypatch):
    monkeypatch.setenv("DB_DRIVER", "PG8000")
    monkeypatch.setenv("DB_SSLMODE", "Require")
    ajustes = get_settings()
    assert (ajustes.db_driver, ajustes.db_sslmode) == ("pg8000", "require")
    assert ajustes.resumen()["db_driver"] == "pg8000"

    monkeypatch.delenv("DB_DRIVER")
    monkeypatch.delenv("DB_SSLMODE")
    get_settings.cache_clear()
    ajustes = get_settings()
    assert (ajustes.db_driver, ajustes.db_sslmode) == ("auto", None)


@pytest.mark.parametrize("nombre, valor", [("DB_DRIVER", "mysql"), ("DB_SSLMODE", "prefer")])
def test_valores_invalidos_se_rechazan_al_arrancar(monkeypatch, nombre, valor):
    monkeypatch.setenv(nombre, valor)
    with pytest.raises(ConfiguracionError, match=nombre):
        get_settings()


# -- engine --------------------------------------------------------------------------------
def test_argumentos_de_conexion_de_psycopg():
    assert connection._argumentos_de_conexion("psycopg", None) == {"connect_timeout": 10}
    assert connection._argumentos_de_conexion("psycopg", "require") == {
        "connect_timeout": 10,
        "sslmode": "require",
    }


def test_argumentos_de_conexion_de_pg8000():
    # pg8000 llama «timeout» al tiempo de espera (con «connect_timeout» fallaría al conectar)
    assert connection._argumentos_de_conexion("pg8000", None) == {"timeout": 10}
    assert connection._argumentos_de_conexion("pg8000", "disable") == {"timeout": 10, "ssl_context": False}
    contexto = connection._argumentos_de_conexion("pg8000", "require")["ssl_context"]
    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.verify_mode == ssl.CERT_NONE and contexto.check_hostname is False


@pytest.mark.parametrize("variables", ["DB_*", "DATABASE_URL"])
def test_engine_usa_pg8000_cuando_psycopg_esta_bloqueado(monkeypatch, variables):
    intentos: list[dict] = []
    pg8000_falso(monkeypatch, intentos)
    monkeypatch.setitem(sys.modules, "psycopg", None)  # DLL bloqueada
    for nombre in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DATABASE_URL", "DB_DRIVER"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("DB_SSLMODE", "require")
    if variables == "DB_*":
        for nombre, valor in dict(
            DB_HOST="servidor.ejemplo", DB_PORT="3002", DB_NAME="appdb", DB_USER="postgres", DB_PASSWORD="clave"
        ).items():
            monkeypatch.setenv(nombre, valor)
    else:  # sin controlador explícito en la URL: la aplicación elige el que funcione
        monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:clave@servidor.ejemplo:3002/appdb")

    engine = connection._crear_engine()
    try:
        assert engine.dialect.driver == "pg8000"
        assert engine.dialect.client_encoding == "utf8"  # tildes y ñ del catálogo
        with pytest.raises(InterfaceError) as error:
            engine.connect()
    finally:
        engine.dispose()

    assert es_error_de_conexion(error.value)
    argumentos = intentos[0]
    assert argumentos["timeout"] == 10 and "connect_timeout" not in argumentos
    assert argumentos["host"] == "servidor.ejemplo" and argumentos["port"] == 3002
    assert argumentos["user"] == "postgres" and argumentos["password"] == "clave"
    assert argumentos["database"] == "appdb"
    assert isinstance(argumentos["ssl_context"], ssl.SSLContext)  # DB_SSLMODE=require


def test_engine_usa_psycopg_si_esta_disponible(monkeypatch):
    pytest.importorskip("psycopg", exc_type=ImportError)  # se omite si el sistema bloquea su DLL
    for nombre, valor in dict(DB_HOST="servidor.ejemplo", DB_PORT="3002", DB_NAME="appdb",
                              DB_USER="postgres", DB_PASSWORD="clave").items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("DATABASE_URL", "DB_DRIVER", "DB_SSLMODE"):
        monkeypatch.delenv(nombre, raising=False)
    engine = connection._crear_engine()  # no abre conexiones
    try:
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


# -- errores independientes del controlador -----------------------------------------------
class _ErrorPsycopg(Exception):
    """Como psycopg: clase específica y atributo sqlstate."""

    sqlstate = "23503"


def test_el_mismo_error_se_describe_igual_con_ambos_controladores():
    mensaje = 'insert or update on table "mediciones" violates foreign key constraint "fk"'
    con_pg8000 = error_servidor(ProgrammingError, "23503", mensaje)
    con_psycopg = ProgrammingError("INSERT", {}, _ErrorPsycopg(mensaje + "\nDETAIL:  Key ... is not present"))
    for error in (con_pg8000, con_psycopg):
        assert codigo_sqlstate(error) == "23503"
        assert describir_error(error) == f"ForeignKeyViolation: {mensaje}"


def test_describir_error_sin_codigo_usa_la_clase_y_la_primera_linea():
    error = OperationalError("SELECT 1", {}, Exception("connection failed: timeout expired\nIs the server running?"))
    assert codigo_sqlstate(error) is None
    assert describir_error(error) == "Exception: connection failed: timeout expired"
    assert describir_error(ValueError("fallo\notra línea")) == "ValueError: fallo"
    assert describir_error(RuntimeError()) == "RuntimeError"


@pytest.mark.parametrize(
    "error, esperado",
    [
        (InterfaceError("SELECT 1", {}, Exception("Can't create a connection")), True),
        (OperationalError("SELECT 1", {}, Exception("connection failed")), True),
        (error_servidor(ProgrammingError, "28P01", "password authentication failed"), True),
        (error_servidor(ProgrammingError, "57P01", "terminating connection"), True),
        (error_servidor(ProgrammingError, "53300", "too many connections"), True),
        (ProgrammingError("SELECT 1", {}, Exception("x"), connection_invalidated=True), True),
        (error_servidor(ProgrammingError, "23503", "violates foreign key constraint"), False),
        (error_servidor(ProgrammingError, "42P01", 'relation "x" does not exist'), False),
        (ValueError("no es de base de datos"), False),
    ],
)
def test_clasificacion_de_errores_de_conexion(error, esperado):
    assert es_error_de_conexion(error) is esperado


@pytest.mark.parametrize(
    "error, contiene",
    [
        (error_servidor(ProgrammingError, "28P01", 'password authentication failed for user "postgres"'), "DB_PASSWORD"),
        (error_servidor(ProgrammingError, "3D000", 'database "otra" does not exist'), "DB_NAME"),
        (error_servidor(ProgrammingError, "28000", 'no pg_hba.conf entry for host "1.2.3.4", no encryption'), "DB_SSLMODE=require"),
        (InterfaceError("SELECT 1", {}, Exception("Server refuses SSL")), "DB_SSLMODE=disable"),
        (InterfaceError("SELECT 1", {}, Exception("Can't create a connection to host x and port 3002")), "DB_HOST"),
    ],
)
def test_pistas_para_los_errores_de_conexion_mas_comunes(error, contiene):
    assert contiene in pista_error_bd(error)


def test_sin_pista_para_errores_que_no_son_de_conexion():
    assert pista_error_bd(error_servidor(ProgrammingError, "23503", "violates foreign key constraint")) is None


# -- API -----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "error, estado",
    [
        (InterfaceError("SELECT 1", {}, Exception("Can't create a connection")), 503),
        (OperationalError("SELECT 1", {}, Exception("connection failed")), 503),
        (error_servidor(ProgrammingError, "28P01", "password authentication failed"), 503),
        (error_servidor(ProgrammingError, "42P01", 'relation "sensores" does not exist'), 500),
    ],
)
def test_la_api_responde_503_si_la_base_no_esta_disponible_y_500_en_otro_caso(client, error, estado):
    def base_rota():
        raise error
        yield  # pragma: no cover - hace de esta función un generador, como get_db

    app.dependency_overrides[get_db] = base_rota
    respuesta = client.get("/sensores")
    assert respuesta.status_code == estado
    assert respuesta.json() == {"detail": "Error al acceder a la base de datos"}
