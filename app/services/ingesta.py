"""Lógica de negocio de la ingesta MQTT.

``procesar_mensaje`` recibe el mensaje crudo que llegó por MQTT, lo valida en capas y
**almacena únicamente si todo es válido**:

1. Decodificación y JSON bien formado.
2. Estructura, campos obligatorios, tipos de datos y formato del timestamp (Pydantic).
3. Timestamp no futuro.
4. Sensor existente, correspondiente al tópico asignado y activo (ORM).
5. Para **cada** magnitud: asociada al sensor, unidad correcta y valor dentro del rango (ORM).
6. Inserción atómica: una fila en ``mediciones`` por magnitud, todas con el mismo
   ``timestamp_utc``. Si alguna magnitud es inválida, no se guarda ninguna.

No levanta excepciones por datos inválidos: devuelve un ``ResultadoIngesta`` que explica el
rechazo. (Los códigos HTTP aplican solo a la API; aquí los errores se registran en el log.)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tiempo import es_futuro
from app.crud import medicion as crud_medicion
from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.errores import describir_error
from app.models.sensor_magnitud import SensorMagnitud
from app.schemas.medicion import MedicionMQTT

logger = logging.getLogger("app.ingesta")

# iot/sensors/{codigo}/data
_PATRON_TOPICO = re.compile(r"^iot/sensors/([^/+#]+)/data$")


class Motivo(str, Enum):
    """Causa por la que un mensaje fue rechazado."""

    PAYLOAD_NO_DECODIFICABLE = "PAYLOAD_NO_DECODIFICABLE"
    JSON_INVALIDO = "JSON_INVALIDO"
    ESTRUCTURA_INVALIDA = "ESTRUCTURA_INVALIDA"
    TIPO_DATO_INVALIDO = "TIPO_DATO_INVALIDO"
    TIMESTAMP_INVALIDO = "TIMESTAMP_INVALIDO"
    SENSOR_INEXISTENTE = "SENSOR_INEXISTENTE"
    SENSOR_NO_ASIGNADO = "SENSOR_NO_ASIGNADO"
    SENSOR_INACTIVO = "SENSOR_INACTIVO"
    MAGNITUD_INVALIDA = "MAGNITUD_INVALIDA"
    UNIDAD_INCORRECTA = "UNIDAD_INCORRECTA"
    VALOR_FUERA_DE_RANGO = "VALOR_FUERA_DE_RANGO"
    ERROR_BASE_DE_DATOS = "ERROR_BASE_DE_DATOS"


@dataclass
class MedicionAlmacenada:
    id: int | None  # None cuando solo se simula (guardar=False)
    magnitud: str
    unidad: str
    valor: Decimal


@dataclass
class ResultadoIngesta:
    almacenado: bool
    valido: bool = False  # superó todas las validaciones (aunque no se haya almacenado)
    motivo: Motivo | None = None
    detalles: list[str] = field(default_factory=list)
    sensor_codigo: str | None = None
    timestamp_utc: datetime | None = None
    mediciones: list[MedicionAlmacenada] = field(default_factory=list)

    def resumen(self) -> str:
        if self.valido:
            filas = ", ".join(
                (f"id={m.id} " if m.id is not None else "")
                + f"{m.magnitud}={m.valor} {m.unidad}"
                for m in self.mediciones
            )
            estado = "ALMACENADO" if self.almacenado else "VALIDO (simulacion: no se almacena)"
            return (
                f"{estado} | sensor={self.sensor_codigo} | "
                f"timestamp_utc={self.timestamp_utc.isoformat()} | {filas}"
            )
        return f"RECHAZADO | motivo={self.motivo.value} | " + " ; ".join(self.detalles)


def codigo_desde_topico(topico: str) -> str | None:
    """Extrae el código del sensor de un tópico ``iot/sensors/{codigo}/data``."""
    coincide = _PATRON_TOPICO.fullmatch(topico)
    return coincide.group(1) if coincide else None


def _rechazo(motivo: Motivo, detalles: list[str] | str, **extra) -> ResultadoIngesta:
    lista = [detalles] if isinstance(detalles, str) else detalles
    return ResultadoIngesta(almacenado=False, motivo=motivo, detalles=lista, **extra)


def _clasificar_errores_pydantic(error: ValidationError) -> tuple[Motivo, list[str]]:
    """Traduce los errores de Pydantic a un motivo de rechazo y un detalle legible."""
    motivos: list[Motivo] = []
    detalles: list[str] = []
    for item in error.errors():
        ubicacion = ".".join(str(parte) for parte in item["loc"]) or "(raíz)"
        tipo = item["type"]
        if item["loc"][:1] == ("timestamp",) and tipo != "missing":
            motivo = Motivo.TIMESTAMP_INVALIDO
        elif tipo in {"missing", "model_type", "dict_type", "too_short", "model_attributes_type"}:
            motivo = Motivo.ESTRUCTURA_INVALIDA
        else:
            motivo = Motivo.TIPO_DATO_INVALIDO
        motivos.append(motivo)
        detalles.append(f"{ubicacion}: {item['msg']}")
    return motivos[0], detalles


def procesar_mensaje(
    db: Session,
    topico: str,
    payload: bytes | str,
    *,
    ahora: datetime | None = None,
    guardar: bool = True,
) -> ResultadoIngesta:
    """Valida un mensaje MQTT y lo almacena solo si supera todas las validaciones.

    Con ``guardar=False`` ejecuta exactamente las mismas validaciones pero no escribe en la
    base de datos (sirve para comprobar mensajes reales sin modificar nada).
    """
    # 1. Decodificación y JSON ------------------------------------------------------------
    try:
        texto = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else payload
    except UnicodeDecodeError as exc:
        return _rechazo(Motivo.PAYLOAD_NO_DECODIFICABLE, f"El payload no es UTF-8 válido: {exc}")

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as exc:
        return _rechazo(Motivo.JSON_INVALIDO, f"JSON mal formado: {exc}")

    # 2. Estructura, tipos y formato del timestamp (Pydantic) -----------------------------
    try:
        mensaje = MedicionMQTT.model_validate(datos)
    except ValidationError as exc:
        motivo, detalles = _clasificar_errores_pydantic(exc)
        return _rechazo(motivo, detalles)

    contexto = {"sensor_codigo": mensaje.sensor_id, "timestamp_utc": mensaje.timestamp}

    # 3. Timestamp no futuro --------------------------------------------------------------
    tolerancia = get_settings().tolerancia_futuro_segundos
    if es_futuro(mensaje.timestamp, tolerancia, ahora):
        return _rechazo(
            Motivo.TIMESTAMP_INVALIDO,
            f"timestamp en el futuro ({mensaje.timestamp.isoformat()}); tolerancia {tolerancia} s",
            **contexto,
        )

    # 4. Sensor (ORM) ---------------------------------------------------------------------
    sensor = crud_sensor.obtener_por_codigo(db, mensaje.sensor_id)
    if sensor is None:
        return _rechazo(
            Motivo.SENSOR_INEXISTENTE,
            f"El sensor '{mensaje.sensor_id}' no existe en el catálogo",
            **contexto,
        )

    codigo_topico = codigo_desde_topico(topico)
    if codigo_topico != sensor.codigo:
        return _rechazo(
            Motivo.SENSOR_NO_ASIGNADO,
            f"El payload es del sensor '{sensor.codigo}' pero llegó por el tópico '{topico}'; "
            "solo se almacenan datos del sensor asignado",
            **contexto,
        )

    if not sensor.activo:
        return _rechazo(
            Motivo.SENSOR_INACTIVO, f"El sensor '{sensor.codigo}' está inactivo", **contexto
        )

    # 5. Magnitudes: relación con el sensor, unidad y rango (ORM) -------------------------
    catalogo = {m.magnitud: m for m in crud_sensor_magnitud.listar_por_sensor(db, sensor.id)}
    errores: list[tuple[Motivo, str]] = []
    validas: list[tuple[SensorMagnitud, Decimal]] = []

    for nombre, item in mensaje.measurements.items():
        configuracion = catalogo.get(nombre)
        if configuracion is None:
            errores.append(
                (
                    Motivo.MAGNITUD_INVALIDA,
                    f"La magnitud '{nombre}' no está asociada al sensor {sensor.codigo} "
                    f"(válidas: {', '.join(sorted(catalogo)) or 'ninguna'})",
                )
            )
            continue

        if item.unit != configuracion.unidad:
            errores.append(
                (
                    Motivo.UNIDAD_INCORRECTA,
                    f"'{nombre}': unidad '{item.unit}' distinta de la esperada "
                    f"'{configuracion.unidad}'",
                )
            )
            continue

        valor = Decimal(str(item.value))
        if not (configuracion.valor_minimo <= valor <= configuracion.valor_maximo):
            errores.append(
                (
                    Motivo.VALOR_FUERA_DE_RANGO,
                    f"'{nombre}': valor {valor} fuera del rango permitido "
                    f"[{configuracion.valor_minimo}, {configuracion.valor_maximo}] "
                    f"{configuracion.unidad}",
                )
            )
            continue

        validas.append((configuracion, valor))

    if errores:  # basta una magnitud inválida para no almacenar nada
        return _rechazo(errores[0][0], [texto_error for _, texto_error in errores], **contexto)

    # 6. Almacenamiento atómico -----------------------------------------------------------
    if not guardar:
        return ResultadoIngesta(
            almacenado=False,
            valido=True,
            sensor_codigo=sensor.codigo,
            timestamp_utc=mensaje.timestamp,
            mediciones=[
                MedicionAlmacenada(id=None, magnitud=c.magnitud, unidad=c.unidad, valor=v)
                for c, v in validas
            ],
        )

    try:
        filas = crud_medicion.crear_varias(
            db, [(config.id, valor) for config, valor in validas], mensaje.timestamp
        )
    except SQLAlchemyError as exc:
        logger.error("No se pudo almacenar la medición: %s", describir_error(exc))
        return _rechazo(
            Motivo.ERROR_BASE_DE_DATOS,
            f"Error de base de datos ({exc.__class__.__name__}); no se almacenó nada",
            **contexto,
        )

    return ResultadoIngesta(
        almacenado=True,
        valido=True,
        sensor_codigo=sensor.codigo,
        timestamp_utc=mensaje.timestamp,
        mediciones=[
            MedicionAlmacenada(
                id=fila.id, magnitud=config.magnitud, unidad=config.unidad, valor=valor
            )
            for fila, (config, valor) in zip(filas, validas)
        ],
    )
