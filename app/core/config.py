"""Configuración de la aplicación a partir de variables de entorno.

Las credenciales y parámetros de conexión se leen del entorno (o del archivo
``.env``, que NO se sube al repositorio). Ver ``.env.example``.
"""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# El .env se busca siempre en la raíz del proyecto (sin depender del directorio desde el que se
# ejecute). No sobrescribe variables que ya existan en el entorno del sistema.
# utf-8-sig: tolera archivos .env guardados con BOM (algunos editores de Windows).
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ_PROYECTO / ".env", encoding="utf-8-sig")

logger = logging.getLogger("app.config")

# Controladores de PostgreSQL soportados, por orden de preferencia, y valores válidos de DB_SSLMODE.
DRIVERS_BD = ("psycopg", "pg8000")
SSLMODES_BD = ("disable", "require")


class ConfiguracionError(RuntimeError):
    """Falta o es inválida una variable de entorno requerida."""


def _texto(nombre: str) -> str | None:
    valor = os.getenv(nombre)
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def _entero(nombre: str, defecto: int) -> int:
    valor = _texto(nombre)
    if valor is None:
        return defecto
    try:
        return int(valor)
    except ValueError as exc:
        raise ConfiguracionError(f"{nombre} debe ser un número entero (valor: {valor!r})") from exc


def _booleano(nombre: str, defecto: bool) -> bool:
    valor = _texto(nombre)
    if valor is None:
        return defecto
    return valor.lower() in {"1", "true", "t", "si", "sí", "yes", "y", "on"}


def _opcion(nombre: str, permitidos: tuple[str, ...], defecto: str | None) -> str | None:
    valor = _texto(nombre)
    if valor is None:
        return defecto
    valor = valor.lower()
    if valor not in permitidos:
        raise ConfiguracionError(
            f"{nombre} debe ser uno de: {', '.join(permitidos)} (valor: {valor!r})"
        )
    return valor


# ---------------------------------------------------------------------------------------
# Controlador de PostgreSQL
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DriverBD:
    """Controlador de PostgreSQL elegido y, si se descartó otro, el motivo."""

    nombre: str
    descartados: tuple[tuple[str, str], ...] = ()

    def descripcion(self) -> str:
        if not self.descartados:
            return self.nombre
        motivos = "; ".join(f"{n} no disponible: {m}" for n, m in self.descartados)
        return f"{self.nombre} ({motivos})"


def _motivo_no_disponible(nombre: str) -> str | None:
    """``None`` si el controlador se puede cargar; si no, el motivo en una sola línea.

    Se captura cualquier excepción: en Windows una directiva de «Control de aplicaciones» puede
    bloquear la DLL de ``psycopg[binary]`` y el ``import`` falla aunque el paquete esté instalado.
    """
    try:
        importlib.import_module(nombre)
    except Exception as exc:  # noqa: BLE001 - ImportError, OSError, etc.
        return f"{exc.__class__.__name__}: {' '.join(str(exc).split())[:400]}"
    return None


@lru_cache
def resolver_driver_bd(preferido: str = "auto") -> DriverBD:
    """Elige el controlador de PostgreSQL.

    ``auto`` prueba ``psycopg`` y, si no se puede cargar, usa ``pg8000`` (Python puro: no depende
    de ninguna DLL que el sistema pueda bloquear).
    """
    if preferido != "auto" and preferido not in DRIVERS_BD:
        raise ConfiguracionError(f"DB_DRIVER debe ser auto, {' o '.join(DRIVERS_BD)}")
    candidatos = DRIVERS_BD if preferido == "auto" else (preferido,)

    descartados: list[tuple[str, str]] = []
    for nombre in candidatos:
        motivo = _motivo_no_disponible(nombre)
        if motivo is None:
            elegido = DriverBD(nombre, tuple(descartados))
            nivel = logging.WARNING if descartados else logging.INFO
            logger.log(nivel, "Controlador PostgreSQL: %s", elegido.descripcion())
            return elegido
        descartados.append((nombre, motivo))

    detalle = "; ".join(f"{n}: {m}" for n, m in descartados)
    raise ConfiguracionError(
        f"No se pudo cargar ningún controlador de PostgreSQL ({detalle}). "
        "Ejecuta: pip install -r requirements.txt (y deja DB_DRIVER=auto en .env)."
    )


@dataclass(frozen=True)
class Settings:
    # PostgreSQL
    db_host: str | None
    db_port: int
    db_name: str | None
    db_user: str | None
    db_password: str | None
    database_url_env: str | None
    # MQTT
    mqtt_enabled: bool
    mqtt_broker: str | None
    mqtt_port: int
    mqtt_topic: str | None
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_keepalive: int
    # Aplicación
    log_level: str
    tolerancia_futuro_segundos: int
    # Controlador y cifrado de PostgreSQL (opcionales)
    db_driver: str = "auto"  # auto | psycopg | pg8000
    db_sslmode: str | None = None  # None = valor por defecto del controlador | disable | require

    @property
    def driver_bd(self) -> DriverBD:
        """Controlador de PostgreSQL que se usará (según ``DB_DRIVER`` y lo que se pueda cargar)."""
        return resolver_driver_bd(self.db_driver)

    @property
    def database_url(self) -> URL | str:
        """URL de conexión a PostgreSQL (o ``DATABASE_URL`` si se define)."""
        if self.database_url_env:
            return self.database_url_env

        requeridas = {
            "DB_HOST": self.db_host,
            "DB_NAME": self.db_name,
            "DB_USER": self.db_user,
            "DB_PASSWORD": self.db_password,
        }
        faltan = [nombre for nombre, valor in requeridas.items() if not valor]
        if faltan:
            raise ConfiguracionError(
                "Faltan variables de entorno para PostgreSQL: "
                + ", ".join(faltan)
                + ". Copia .env.example a .env y complétalo."
            )
        # URL.create escapa correctamente caracteres especiales de la contraseña.
        return URL.create(
            f"postgresql+{self.driver_bd.nombre}",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    def validar_mqtt(self) -> None:
        """Valida la configuración MQTT (se llama al iniciar el consumidor)."""
        faltan = [
            nombre
            for nombre, valor in (("MQTT_BROKER", self.mqtt_broker), ("MQTT_TOPIC", self.mqtt_topic))
            if not valor
        ]
        if faltan:
            raise ConfiguracionError(
                "Faltan variables de entorno para MQTT: "
                + ", ".join(faltan)
                + ". Copia .env.example a .env y complétalo (o usa MQTT_ENABLED=false)."
            )
        if "+" in self.mqtt_topic or "#" in self.mqtt_topic:
            raise ConfiguracionError(
                "MQTT_TOPIC debe ser el tópico exacto del sensor asignado, sin comodines (+ ni #)."
            )

    def resumen(self) -> dict[str, object]:
        """Resumen de la configuración sin secretos (para registros de ejecución).

        El host de la base de datos tampoco se registra: los logs pueden terminar en el repositorio.
        """
        return {
            "db_host": "(definido en .env)" if self.db_host else None,
            "db_port": self.db_port,
            "db_name": self.db_name,
            "db_user": self.db_user,
            "db_driver": self.db_driver,
            "db_sslmode": self.db_sslmode,
            "mqtt_enabled": self.mqtt_enabled,
            "mqtt_broker": self.mqtt_broker,
            "mqtt_port": self.mqtt_port,
            "mqtt_topic": self.mqtt_topic,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings(
        db_host=_texto("DB_HOST"),
        db_port=_entero("DB_PORT", 5432),
        db_name=_texto("DB_NAME"),
        db_user=_texto("DB_USER"),
        db_password=os.getenv("DB_PASSWORD") or None,
        database_url_env=_texto("DATABASE_URL"),
        mqtt_enabled=_booleano("MQTT_ENABLED", True),
        mqtt_broker=_texto("MQTT_BROKER"),
        mqtt_port=_entero("MQTT_PORT", 1883),
        mqtt_topic=_texto("MQTT_TOPIC"),
        mqtt_username=_texto("MQTT_USERNAME"),
        mqtt_password=os.getenv("MQTT_PASSWORD") or None,
        mqtt_keepalive=_entero("MQTT_KEEPALIVE", 60),
        log_level=(_texto("LOG_LEVEL") or "INFO").upper(),
        tolerancia_futuro_segundos=_entero("TIMESTAMP_TOLERANCIA_FUTURO_SEGUNDOS", 600),
        db_driver=_opcion("DB_DRIVER", ("auto", *DRIVERS_BD), "auto"),
        db_sslmode=_opcion("DB_SSLMODE", SSLMODES_BD, None),
    )
