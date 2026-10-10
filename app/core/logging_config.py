"""Registros de ejecución (consola + archivo ``logs/app.log``).

Los registros del procesamiento MQTT sirven como evidencia: muestran cada mensaje
recibido y si fue ALMACENADO o RECHAZADO (y por qué).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
DIRECTORIO_LOGS = RAIZ_PROYECTO / "logs"
FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def configurar_logging(nivel: str = "INFO", *, archivo: bool = True) -> None:
    """Configura el logger ``app`` (idempotente: no duplica manejadores al recargar)."""
    logger = logging.getLogger("app")
    logger.setLevel(nivel)
    logger.propagate = False
    if logger.handlers:
        return

    formato = logging.Formatter(FORMATO, FORMATO_FECHA)

    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    logger.addHandler(consola)

    if archivo:
        try:
            DIRECTORIO_LOGS.mkdir(exist_ok=True)
            manejador = RotatingFileHandler(
                DIRECTORIO_LOGS / "app.log",
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            manejador.setFormatter(formato)
            logger.addHandler(manejador)
        except OSError as exc:  # pragma: no cover - disco de solo lectura, etc.
            logger.warning("No se pudo crear logs/app.log: %s", exc)
