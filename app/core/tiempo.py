"""Utilidades de fecha y hora.

Regla del taller: los datos se **almacenan en UTC** y las respuestas GET se
**muestran en hora local de Colombia** (America/Bogota, UTC-05:00, sin horario
de verano) con un formato único: ``AAAA-MM-DDThh:mm:ss-05:00``.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
NOMBRE_ZONA = "America/Bogota"

# Fecha ISO 8601: AAAA-MM-DD[Thh:mm[:ss[.fff]]][Z|±hh:mm]
_PATRON_ISO = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?)?"
    r"(Z|[+-]\d{2}:\d{2})?$"
)
_SOLO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Un '+' sin codificar en la URL llega como espacio: 2026-10-07T11:00:00 05:00
_MAS_PERDIDO = re.compile(r"(T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?) (\d{2}:\d{2})$")


@lru_cache
def zona_colombia() -> tzinfo:
    """Zona horaria de Colombia (usa ``tzdata`` en Windows)."""
    try:
        return ZoneInfo(NOMBRE_ZONA)
    except ZoneInfoNotFoundError:  # pragma: no cover - solo si falta tzdata
        return timezone(timedelta(hours=-5), "COT")


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def a_utc(valor: datetime) -> datetime:
    """Normaliza a UTC. Un datetime sin zona se asume UTC (así los devuelve SQLite)."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def a_hora_colombia(valor: datetime) -> datetime:
    """Convierte un instante (UTC o con zona) a hora local de Colombia."""
    return a_utc(valor).astimezone(zona_colombia())


def formatear_local(valor: datetime) -> str:
    """Formato legible y consistente para las respuestas GET: 2026-10-07T11:25:30-05:00."""
    return a_hora_colombia(valor).isoformat(timespec="seconds")


def parsear_iso8601(
    texto: str,
    *,
    requerir_hora: bool,
    requerir_zona: bool,
    zona_defecto: tzinfo | None = None,
) -> datetime:
    """Interpreta una fecha ISO 8601 o lanza ``ValueError`` con un mensaje claro."""
    if not isinstance(texto, str):
        raise ValueError("debe ser texto en formato ISO 8601")

    coincide = _PATRON_ISO.fullmatch(texto.strip())
    if coincide is None:
        raise ValueError(
            "formato no reconocido; use ISO 8601, por ejemplo 2026-10-07T16:25:30Z"
        )

    anio, mes, dia, hora, minuto, segundo, fraccion, zona = coincide.groups()
    if hora is None and (requerir_hora or zona is not None):
        raise ValueError("falta la hora (hh:mm:ss)")
    if zona is None and requerir_zona:
        raise ValueError("falta la zona horaria (use Z o ±hh:mm)")

    if zona is None:
        tz = zona_defecto
    elif zona == "Z":
        tz = UTC
    else:
        desplazamiento = timedelta(hours=int(zona[1:3]), minutes=int(zona[4:6]))
        try:
            tz = timezone(desplazamiento if zona[0] == "+" else -desplazamiento)
        except ValueError as exc:
            raise ValueError(f"zona horaria fuera de rango ({zona})") from exc

    microsegundos = int((fraccion or "0").ljust(9, "0")[:6])
    try:
        return datetime(
            int(anio),
            int(mes),
            int(dia),
            int(hora or 0),
            int(minuto or 0),
            int(segundo or 0),
            microsegundos,
            tzinfo=tz,
        )
    except ValueError as exc:
        raise ValueError(f"fecha u hora inexistente ({texto.strip()})") from exc


def parsear_timestamp_mqtt(texto: str) -> datetime:
    """Timestamp de un mensaje MQTT: ISO 8601 completo y con zona; se devuelve en UTC."""
    return parsear_iso8601(texto, requerir_hora=True, requerir_zona=True).astimezone(UTC)


def parsear_filtro_fecha(texto: str, *, fin_de_dia: bool = False) -> datetime:
    """Parámetros ``desde`` / ``hasta`` de las consultas; se devuelve en UTC.

    * Con zona (``Z`` o ``±hh:mm``) se respeta tal cual.
    * Sin zona se interpreta como hora de Colombia (la misma que muestran los GET).
    * Solo fecha (``2026-10-07``): ``desde`` = 00:00:00 y ``hasta`` = 23:59:59.999999.
    """
    texto = _MAS_PERDIDO.sub(r"\1+\2", texto.strip())
    solo_fecha = _SOLO_FECHA.fullmatch(texto) is not None
    valor = parsear_iso8601(
        texto, requerir_hora=False, requerir_zona=False, zona_defecto=zona_colombia()
    )
    if solo_fecha and fin_de_dia:
        valor = valor + timedelta(days=1) - timedelta(microseconds=1)
    return a_utc(valor)


def es_futuro(instante_utc: datetime, tolerancia_segundos: int, ahora: datetime | None = None) -> bool:
    """True si el instante supera a «ahora» en más de la tolerancia permitida."""
    referencia = a_utc(ahora) if ahora is not None else ahora_utc()
    return a_utc(instante_utc) > referencia + timedelta(seconds=tolerancia_segundos)
