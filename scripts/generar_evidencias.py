from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import ConfiguracionError, get_settings
from app.core.tiempo import UTC, a_utc, ahora_utc, formatear_local, parsear_timestamp_mqtt
from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_engine, get_session_factory
from app.database.errores import codigo_sqlstate, describir_error, pista_error_bd
from app.models import Medicion, SensorMagnitud
from app.services.ingesta import Motivo, codigo_desde_topico, procesar_mensaje

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIAS = RAIZ / "evidencias"
LOGS = RAIZ / "logs"
MARCA_TS = "2026-01-01T00:00:00Z" 
def hora_local() -> str:
    return formatear_local(ahora_utc()).replace("T", " ")


def consola_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def json_md(objeto) -> str:
    return "```json\n" + json.dumps(objeto, indent=2, ensure_ascii=False, default=str) + "\n```"


def texto_md(texto: str) -> str:
    return "```text\n" + texto.rstrip() + "\n```"


def recortar(cuerpo, maximo: int = 3):
    if isinstance(cuerpo, list) and len(cuerpo) > maximo:
        return cuerpo[:maximo] + [f"... ({len(cuerpo) - maximo} elementos más)"]
    return cuerpo


@dataclass
class Prueba:
    numero: str
    titulo: str
    archivo: str
    implementacion: list[str]
    explicacion: str
    estado: str = "PENDIENTE"  # OK | FALLO | SIN DATOS | PENDIENTE
    entrada: str = ""
    resultado: str = ""
    http: str = "No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log)."
    registro: str = ""
    notas: list[str] = field(default_factory=list)

    def a_markdown(self) -> str:
        impl = "\n".join(f"- {linea}" for linea in self.implementacion)
        notas = ("\n## Observaciones\n" + "\n".join(f"- {n}" for n in self.notas) + "\n") if self.notas else ""
        return f"""# Prueba {self.numero} — {self.titulo}

**Estado:** {self.estado} · **Generado:** {hora_local()} (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
{self.entrada.strip()}

## Resultado obtenido
{self.resultado.strip()}

## Código HTTP
{self.http.strip()}

## Registro almacenado o rechazado
{self.registro.strip()}

## Archivo y función donde se implementa
{impl}

## Explicación
{self.explicacion.strip()}
{notas}"""

    def guardar(self) -> None:
        EVIDENCIAS.mkdir(exist_ok=True)
        (EVIDENCIAS / self.archivo).write_text(self.a_markdown(), encoding="utf-8")
        print(f"  [{self.estado:<9}] {self.numero:>5}  {self.titulo}")


@contextmanager
def sesion_revertible():
    """Sesión cuyos «commit» solo liberan un savepoint: al salir todo se revierte siempre."""
    conexion = get_engine().connect()
    transaccion = conexion.begin()
    sesion = Session(
        bind=conexion,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


_LINEA_LOG = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| (app\.[\w.]+) \| (.*)$")


def analizar_log() -> dict | None:
    archivos = [LOGS / n for n in ("app.log.3", "app.log.2", "app.log.1", "app.log")]
    archivos = [a for a in archivos if a.exists()]
    if not archivos:
        return None

    info = {
        "recibidos": 0,
        "almacenados": 0,
        "rechazados": Counter(),
        "ejemplos": {},
        "ejemplo_recibido": None,
        "ejemplo_almacenado": None,
        "desde": None,
        "hasta": None,
    }
    for archivo in archivos:
        for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _LINEA_LOG.match(linea)
            if not m or m.group(3) != "app.mqtt":
                continue
            momento, mensaje = m.group(1), m.group(4)
            info["desde"] = info["desde"] or momento
            info["hasta"] = momento
            if mensaje.startswith("MENSAJE RECIBIDO"):
                info["recibidos"] += 1
                info["ejemplo_recibido"] = info["ejemplo_recibido"] or linea
            elif mensaje.startswith("ALMACENADO"):
                info["almacenados"] += 1
                info["ejemplo_almacenado"] = info["ejemplo_almacenado"] or linea
            elif mensaje.startswith("RECHAZADO"):
                motivo = re.search(r"motivo=(\w+)", mensaje)
                clave = motivo.group(1) if motivo else "DESCONOCIDO"
                info["rechazados"][clave] += 1
                info["ejemplos"].setdefault(clave, linea)
    return info


def guardar_extracto_log(maximo_inicio: int = 60, maximo_final: int = 300) -> int:
    archivo = LOGS / "app.log"
    if not archivo.exists():
        return 0
    lineas = [
        re.sub(r"('db_host': ')[^']*(')", r"\1(oculto)\2", linea)
        for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines()
    ]
    if len(lineas) > maximo_inicio + maximo_final:
        omitidas = len(lineas) - maximo_inicio - maximo_final
        lineas = lineas[:maximo_inicio] + [f"... ({omitidas} líneas omitidas) ..."] + lineas[-maximo_final:]
    cabecera = (
        "Extracto del registro de ejecución (logs/app.log) generado por scripts/generar_evidencias.py\n"
        f"Generado: {hora_local()} (hora de Colombia). El log completo no se versiona (*.log está en .gitignore).\n"
        + "=" * 100
    )
    EVIDENCIAS.mkdir(exist_ok=True)
    (EVIDENCIAS / "registro_ejecucion.txt").write_text(cabecera + "\n" + "\n".join(lineas) + "\n", encoding="utf-8")
    return len(lineas)


def bloque_log(log: dict | None, motivo: Motivo) -> str:
    if log is None:
        return "No se encontró `logs/app.log` (la aplicación aún no se ha ejecutado en este equipo)."
    n = log["rechazados"].get(motivo.value, 0)
    if n == 0:
        return f"En `logs/app.log` no hay mensajes reales rechazados por `{motivo.value}` durante la captura."
    return (
        f"Durante la captura, el consumidor rechazó **{n}** mensaje(s) reales por `{motivo.value}`. "
        f"Ejemplo tomado de `logs/app.log`:\n\n{texto_md(log['ejemplos'][motivo.value])}"
    )


@dataclass
class Contexto:
    codigo: str
    topico: str
    sensor_id: int
    sensor: dict
    magnitudes: list[dict]
    ids_magnitud: list[int]
    total: int
    t_min: datetime | None
    t_max: datetime | None
    filas: list[tuple] 

    @property
    def minutos(self) -> float:
        if self.t_min is None or self.t_max is None:
            return 0.0
        return (self.t_max - self.t_min).total_seconds() / 60

    @property
    def minutos_continuos(self) -> float:
        instantes = sorted({ts for _, _, ts in self.filas})
        if len(instantes) < 2:
            return 0.0
        pasos = [(b - a).total_seconds() for a, b in zip(instantes, instantes[1:])]
        limite = max(300.0, 10 * sorted(pasos)[len(pasos) // 2])
        mejor = actual = 0.0
        for paso in pasos:
            actual = actual + paso if paso <= limite else 0.0
            mejor = max(mejor, actual)
        return mejor / 60


def cargar_contexto(db: Session, topico: str) -> Contexto:
    codigo = codigo_desde_topico(topico)
    if not codigo:
        raise ConfiguracionError(f"MQTT_TOPIC no tiene el formato iot/sensors/<codigo>/data: {topico}")
    sensor = crud_sensor.obtener_por_codigo(db, codigo)
    if sensor is None:
        raise ConfiguracionError(f"El sensor '{codigo}' no existe en la base de datos")
    magnitudes = crud_sensor_magnitud.listar_por_sensor(db, sensor.id)
    ids = [m.id for m in magnitudes]
    filas = db.execute(
        select(Medicion.id, SensorMagnitud.magnitud, Medicion.timestamp_utc)
        .join(SensorMagnitud, SensorMagnitud.id == Medicion.sensor_magnitud_id)
        .where(Medicion.sensor_magnitud_id.in_(ids))
        .order_by(Medicion.timestamp_utc.desc(), Medicion.id.desc())
    ).all()
    filas = [(i, mag, a_utc(ts)) for i, mag, ts in filas]
    return Contexto(
        codigo=codigo,
        topico=topico,
        sensor_id=sensor.id,
        sensor=dict(id=sensor.id, codigo=sensor.codigo, nombre=sensor.nombre,
                    categoria=sensor.categoria, ubicacion=sensor.ubicacion, activo=sensor.activo),
        magnitudes=[
            dict(id=m.id, magnitud=m.magnitud, unidad=m.unidad,
                 minimo=m.valor_minimo, maximo=m.valor_maximo)
            for m in magnitudes
        ],
        ids_magnitud=ids,
        total=len(filas),
        t_min=filas[-1][2] if filas else None,
        t_max=filas[0][2] if filas else None,
        filas=filas,
    )


def total_actual(db: Session, ctx: Contexto) -> int:
    return db.scalar(
        select(func.count()).select_from(Medicion).where(Medicion.sensor_magnitud_id.in_(ctx.ids_magnitud))
    )


def iso_z(instante: datetime) -> str:
    return a_utc(instante).strftime("%Y-%m-%dT%H:%M:%SZ")


def crear_cliente(url: str | None):
    if url:
        return httpx.Client(base_url=url.rstrip("/"), timeout=30), f"el servidor HTTP en {url}"
    from app.main import app  # import tardío: no arranca el consumidor MQTT

    return TestClient(app), "la aplicación FastAPI en proceso (TestClient, sin lifespan ni MQTT)"


def llamar(cliente, ruta: str, **parametros) -> dict:
    respuesta = cliente.get(ruta, params=parametros or None)
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = respuesta.text
    return {
        "peticion": f"GET {respuesta.request.url.raw_path.decode()}",
        "estado": respuesta.status_code,
        "cuerpo": cuerpo,
    }


def bloque_http(r: dict, maximo: int = 3) -> str:
    return (
        f"```http\n{r['peticion']}\n```\n\n"
        f"Respuesta **HTTP {r['estado']}**:\n\n{json_md(recortar(r['cuerpo'], maximo))}"
    )


def sin_datos(p: Prueba, motivo: str) -> Prueba:
    p.estado = "SIN DATOS"
    p.entrada = p.entrada or "No se pudo preparar la prueba."
    p.resultado = motivo
    p.http = p.http if p.http else "-"
    p.registro = "No aplica."
    return p


def prueba_1(ctx: Contexto, log: dict | None) -> Prueba:
    p = Prueba(
        "1", "Recepción MQTT desde el tópico asignado", "01_recepcion_mqtt.md",
        ["`app/mqtt/client.py` → `ClienteMQTT._al_conectar` (suscripción al tópico asignado, QoS 1)",
         "`app/mqtt/client.py` → `ClienteMQTT._al_recibir` (recepción y registro de cada mensaje)"],
        "El consumidor se conecta al broker, se suscribe únicamente al tópico del sensor asignado y "
        "registra cada mensaje recibido. La captura inicial de mensajes reales (con el análisis de su "
        "estructura) está en `00_captura_mqtt_inicial.md`; aquí se resume lo que registró la aplicación "
        "durante toda la ejecución.",
    )
    p.entrada = f"Tópico suscrito: `{ctx.topico}`."
    existe = (EVIDENCIAS / "00_captura_mqtt_inicial.md").exists()
    if log is None:
        p.estado = "SIN DATOS"
        p.resultado = "No existe `logs/app.log`: ejecuta la aplicación (`uvicorn app.main:app`) y vuelve a generar."
        p.registro = "No aplica."
        return p

    filas = "\n".join(f"| `{m}` | {n} |" for m, n in sorted(log["rechazados"].items())) or "| (ninguno) | 0 |"
    p.resultado = (
        f"Ventana de ejecución registrada: {log['desde']} a {log['hasta']} (hora local del equipo).\n\n"
        f"- Mensajes recibidos: **{log['recibidos']}**\n- Almacenados: **{log['almacenados']}**\n"
        f"- Rechazados: **{sum(log['rechazados'].values())}**\n\n"
        f"| Motivo de rechazo | Cantidad |\n|---|---|\n{filas}\n\n"
        f"Primer mensaje recibido (extracto de `logs/app.log`):\n\n{texto_md(log['ejemplo_recibido'] or '-')}"
    )
    p.registro = "Los mensajes aceptados y rechazados quedan en `logs/app.log` (ver pruebas 2 a 7)."
    if existe:
        p.notas.append("Captura de mensajes reales con su análisis: `00_captura_mqtt_inicial.md`.")
    else:
        p.notas.append("Falta `00_captura_mqtt_inicial.md`: ejecuta `python -m scripts.verificar_conexiones`.")
    p.estado = "OK" if log["recibidos"] > 0 else "SIN DATOS"
    return p


def prueba_2(ctx: Contexto, db: Session, log: dict | None) -> Prueba:
    p = Prueba(
        "2", "Medición válida almacenada en PostgreSQL", "02_medicion_almacenada.md",
        ["`app/services/ingesta.py` → `procesar_mensaje` (paso 6: almacenamiento atómico)",
         "`app/crud/medicion.py` → `crear_varias` (una fila por magnitud, mismo `timestamp_utc`)",
         "`app/models/medicion.py` → `Medicion`"],
        "Cuando un mensaje supera todas las validaciones se inserta una fila en `mediciones` por cada "
        "magnitud del payload, todas con el mismo `timestamp_utc` y en una sola transacción. El instante "
        "se guarda en UTC; la columna `fecha_recepcion` la asigna PostgreSQL (`DEFAULT NOW()`).",
    )
    p.entrada = (
        f"Mensajes reales publicados por el sensor `{ctx.codigo}` y procesados por la aplicación "
        f"en ejecución (tópico `{ctx.topico}`)."
    )
    if ctx.total == 0:
        return sin_datos(p, "Todavía no hay mediciones del sensor en la base: deja correr la aplicación.")

    ultimas = db.execute(
        select(Medicion, SensorMagnitud.magnitud, SensorMagnitud.unidad)
        .join(SensorMagnitud, SensorMagnitud.id == Medicion.sensor_magnitud_id)
        .where(Medicion.sensor_magnitud_id.in_(ctx.ids_magnitud))
        .order_by(Medicion.timestamp_utc.desc(), Medicion.id.desc())
        .limit(6)
    ).all()
    tabla = "\n".join(
        f"| {m.id} | {m.sensor_magnitud_id} | `{mag}` | {m.valor} {uni} | {a_utc(m.timestamp_utc).isoformat()} "
        f"| {a_utc(m.fecha_recepcion).isoformat()} |"
        for m, mag, uni in ultimas
    )
    por_magnitud = Counter(mag for _, mag, _ in ctx.filas)
    cuenta = "\n".join(f"| `{m}` | {n} |" for m, n in sorted(por_magnitud.items()))
    por_ts = Counter(ts for _, _, ts in ctx.filas)
    grupos = "\n".join(
        f"| {ts.isoformat()} | {n} |" for ts, n in sorted(por_ts.items(), reverse=True)[:5]
    )
    p.resultado = (
        f"- Filas almacenadas del sensor `{ctx.codigo}`: **{ctx.total}**\n"
        f"- Primera medición (UTC): {ctx.t_min.isoformat()}\n- Última medición (UTC): {ctx.t_max.isoformat()}\n"
        f"- Ventana entre la primera y la última medición: {ctx.minutos:.1f} minutos\n"
        f"- Tramo continuo de captura más largo: **{ctx.minutos_continuos:.1f} minutos** (la guía exige al menos 20)\n\n"
        f"Últimas filas en la tabla `mediciones` (valores tal como están en PostgreSQL):\n\n"
        f"| id | sensor_magnitud_id | magnitud | valor | timestamp_utc | fecha_recepcion |\n|---|---|---|---|---|---|\n{tabla}\n\n"
        f"Filas por magnitud:\n\n| Magnitud | Filas |\n|---|---|\n{cuenta}\n\n"
        f"Todas las magnitudes de un mismo mensaje comparten `timestamp_utc` "
        f"(últimos 5 instantes y cuántas filas tiene cada uno):\n\n| timestamp_utc | filas |\n|---|---|\n{grupos}"
    )
    p.registro = f"ALMACENADO: {ctx.total} registros del sensor `{ctx.codigo}` en PostgreSQL."
    if log is not None:
        p.registro += f" El log reporta {log['almacenados']} mensajes almacenados."
    if ctx.minutos_continuos < 20:
        p.notas.append(
            f"ADVERTENCIA: el tramo continuo de captura es de {ctx.minutos_continuos:.1f} min; la guía pide al menos 20 min. "
            "Deja correr la aplicación más tiempo y vuelve a generar las evidencias."
        )
    p.estado = "OK"
    return p


def valor_tipico(m: dict) -> float:
    minimo, maximo = float(m["minimo"]), float(m["maximo"])
    return round(minimo + (maximo - minimo) * 0.432198, 4)  # valor «marcador» dentro del rango


def payload_base(ctx: Contexto) -> dict:
    return {
        "sensor_id": ctx.codigo,
        "timestamp": MARCA_TS,
        "measurements": {
            m["magnitud"]: {"value": valor_tipico(m), "unit": m["unidad"]} for m in ctx.magnitudes
        },
    }


class EjecutorRechazos:

    def __init__(self, ctx: Contexto, sesion: Session):
        self.ctx, self.sesion = ctx, sesion
        self.id_antes = sesion.scalar(select(func.max(Medicion.id))) or 0
        self.marca = parsear_timestamp_mqtt(MARCA_TS)
        self.valores_marca = [Decimal(str(valor_tipico(m))) for m in ctx.magnitudes]

    def filas_de_prueba(self) -> int:
        return self.sesion.scalar(
            select(func.count()).select_from(Medicion).where(
                Medicion.id > self.id_antes,
                or_(Medicion.timestamp_utc == self.marca, Medicion.valor.in_(self.valores_marca)),
            )
        )

    def probar(self, payload: dict | str, esperado: Motivo, topico: str | None = None):
        crudo = payload if isinstance(payload, str) else json.dumps(payload)
        resultado = procesar_mensaje(self.sesion, topico or self.ctx.topico, crudo)
        filas = self.filas_de_prueba()
        correcto = (not resultado.almacenado) and resultado.motivo is esperado and filas == 0
        return resultado, filas, correcto


def prueba_rechazo(
    ejecutor: EjecutorRechazos,
    log: dict | None,
    *,
    numero: str,
    titulo: str,
    archivo: str,
    payload: dict | str,
    esperado: Motivo,
    implementacion: list[str],
    explicacion: str,
    descripcion_cambio: str,
    topico: str | None = None,
) -> Prueba:
    p = Prueba(numero, titulo, archivo, implementacion, explicacion)
    resultado, filas, correcto = ejecutor.probar(payload, esperado, topico)
    p.entrada = (
        f"Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `{topico or ejecutor.ctx.topico}` "
        f"(la misma función que invoca el consumidor MQTT) — {descripcion_cambio}\n\n"
        + (json_md(payload) if isinstance(payload, dict) else texto_md(payload))
    )
    p.resultado = (
        f"Resultado del procesamiento:\n\n{texto_md(resultado.resumen())}\n\n"
        f"Motivo esperado: `{esperado.value}` · obtenido: `{resultado.motivo.value if resultado.motivo else 'ninguno'}`."
    )
    p.registro = (
        f"**{'RECHAZADO' if not resultado.almacenado else 'ALMACENADO (incorrecto)'}**. "
        f"Filas insertadas en `mediciones` con los datos de esta prueba: **{filas}** "
        "(la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).\n\n"
        + bloque_log(log, esperado)
    )
    p.estado = "OK" if correcto else "FALLO"
    return p


def pruebas_de_rechazo(ctx: Contexto, log: dict | None) -> list[Prueba]:
    pruebas: list[Prueba] = []
    primera = ctx.magnitudes[0]
    nombre_1 = primera["magnitud"]

    with sesion_revertible() as sesion:
        ej = EjecutorRechazos(ctx, sesion)

        p = payload_base(ctx)
        p["sensor_id"] = "NO-EXISTE-999"
        pruebas.append(prueba_rechazo(
            ej, log, numero="3", titulo="Sensor inexistente", archivo="03_sensor_inexistente.md",
            payload=p, esperado=Motivo.SENSOR_INEXISTENTE,
            descripcion_cambio="`sensor_id` que no existe en la tabla `sensores`.",
            implementacion=["`app/services/ingesta.py` → `procesar_mensaje` (paso 4: sensor existente)",
                            "`app/crud/sensor.py` → `obtener_por_codigo`"],
            explicacion="Tras validar la estructura, la aplicación busca el sensor por `codigo` mediante el ORM. "
                        "Si no existe, el mensaje se descarta y nada se escribe.",
        ))

        p = payload_base(ctx)
        p["measurements"][nombre_1]["unit"] = "unidad-incorrecta"
        pruebas.append(prueba_rechazo(
            ej, log, numero="4", titulo="Unidad incorrecta", archivo="04_unidad_incorrecta.md",
            payload=p, esperado=Motivo.UNIDAD_INCORRECTA,
            descripcion_cambio=f"la unidad de `{nombre_1}` no coincide con `{primera['unidad']}` (la del catálogo).",
            implementacion=["`app/services/ingesta.py` → `procesar_mensaje` (paso 5: unidad)",
                            "`app/crud/sensor_magnitud.py` → `listar_por_sensor`"],
            explicacion="Cada magnitud se compara con su configuración en `sensor_magnitudes`; la unidad debe "
                        "ser exactamente la registrada.",
        ))

        p = payload_base(ctx)
        p["measurements"][nombre_1]["value"] = "abc"
        pruebas.append(prueba_rechazo(
            ej, log, numero="5", titulo="Tipo de dato incorrecto", archivo="05_tipo_dato_incorrecto.md",
            payload=p, esperado=Motivo.TIPO_DATO_INVALIDO,
            descripcion_cambio=f"`value` de `{nombre_1}` es texto en lugar de número.",
            implementacion=["`app/schemas/medicion.py` → `MagnitudMQTT` (modelo Pydantic estricto: `value: float`)",
                            "`app/services/ingesta.py` → `_clasificar_errores_pydantic`"],
            explicacion="Pydantic valida los tipos antes de tocar la base de datos. El modo estricto impide que "
                        "se acepte `\"412.5\"`, `true` o `null` como número.",
        ))

        p = payload_base(ctx)
        medidas = p["measurements"]
        medidas["magnitud_inexistente"] = medidas.pop(nombre_1)
        pruebas.append(prueba_rechazo(
            ej, log, numero="6", titulo="Magnitud incorrecta", archivo="06_magnitud_incorrecta.md",
            payload=p, esperado=Motivo.MAGNITUD_INVALIDA,
            descripcion_cambio=f"se reemplazó la magnitud `{nombre_1}` por `magnitud_inexistente`.",
            implementacion=["`app/services/ingesta.py` → `procesar_mensaje` (paso 5: relación sensor-magnitud)",
                            "`app/crud/sensor_magnitud.py` → `listar_por_sensor`"],
            explicacion="Solo se aceptan las magnitudes asociadas al sensor en `sensor_magnitudes`.",
        ))

        p = payload_base(ctx)
        p["timestamp"] = "no-es-una-fecha"
        pruebas.append(prueba_rechazo(
            ej, log, numero="7", titulo="Timestamp inválido", archivo="07_timestamp_invalido.md",
            payload=p, esperado=Motivo.TIMESTAMP_INVALIDO,
            descripcion_cambio="`timestamp` no es una fecha ISO 8601.",
            implementacion=["`app/schemas/medicion.py` → `_validar_timestamp` (validador del campo `timestamp`)",
                            "`app/core/tiempo.py` → `parsear_timestamp_mqtt`"],
            explicacion="El timestamp debe ser ISO 8601 completo y con zona horaria (por ejemplo "
                        "`2026-10-07T16:25:30Z`); se normaliza a UTC. Los valores inexistentes "
                        "(`2026-13-45T...`), sin zona o numéricos también se rechazan (ver `tests/`).",
        ))

        # ---- pruebas adicionales ---------------------------------------------------------
        extras: list[Prueba] = []
        p = payload_base(ctx)
        p["measurements"][nombre_1]["value"] = float(primera["maximo"]) + (float(primera["maximo"]) - float(primera["minimo"])) + 1
        ej.valores_marca.append(Decimal(str(p["measurements"][nombre_1]["value"])))
        extras.append(prueba_rechazo(
            ej, log, numero="A", titulo="Valor fuera de rango", archivo="_a", payload=p,
            esperado=Motivo.VALOR_FUERA_DE_RANGO, implementacion=[], explicacion="",
            descripcion_cambio=f"`{nombre_1}` supera `valor_maximo` ({primera['maximo']}).",
        ))

        if len(ctx.magnitudes) >= 2:
            p = payload_base(ctx)
            segunda = ctx.magnitudes[1]["magnitud"]
            p["measurements"][segunda]["unit"] = "unidad-incorrecta"
            extras.append(prueba_rechazo(
                ej, log, numero="B", titulo="Todo o nada", archivo="_b", payload=p,
                esperado=Motivo.UNIDAD_INCORRECTA, implementacion=[], explicacion="",
                descripcion_cambio=f"`{nombre_1}` es válida pero `{segunda}` trae una unidad incorrecta: no se debe guardar ninguna.",
            ))

        otros = [s for s in _otros_sensores(sesion, ctx.codigo)]
        if otros:
            ajeno, magnitudes_ajenas = otros[0]
            p = {
                "sensor_id": ajeno,
                "timestamp": MARCA_TS,
                "measurements": {m.magnitud: {"value": valor_tipico(dict(minimo=m.valor_minimo, maximo=m.valor_maximo)), "unit": m.unidad} for m in magnitudes_ajenas},
            }
            extras.append(prueba_rechazo(
                ej, log, numero="C", titulo="Sensor de otro grupo", archivo="_c", payload=p,
                esperado=Motivo.SENSOR_NO_ASIGNADO, implementacion=[], explicacion="",
                descripcion_cambio=f"el sensor `{ajeno}` existe, pero no es el asignado (`{ctx.codigo}`).",
            ))
            marcado = sesion.scalar(
                select(func.count()).select_from(Medicion)
                .join(SensorMagnitud, SensorMagnitud.id == Medicion.sensor_magnitud_id)
                .join(SensorMagnitud.sensor)
                .where(Medicion.id > ej.id_antes, Medicion.timestamp_utc == ej.marca)
            )
            extras[-1].registro += f"\n\nFilas con el timestamp de prueba en cualquier sensor: **{marcado}**."

        p = payload_base(ctx)
        p["timestamp"] = (ahora_utc() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        extras.append(prueba_rechazo(
            ej, log, numero="D", titulo="Timestamp en el futuro", archivo="_d", payload=p,
            esperado=Motivo.TIMESTAMP_INVALIDO, implementacion=[], explicacion="",
            descripcion_cambio="el timestamp es de mañana.",
        ))
        pruebas.append(_unir_extras(extras))

    return pruebas


def _otros_sensores(sesion: Session, codigo: str):
    for sensor in crud_sensor.listar(sesion, activo=True, limit=50):
        if sensor.codigo != codigo:
            magnitudes = crud_sensor_magnitud.listar_por_sensor(sesion, sensor.id)
            if magnitudes:
                yield sensor.codigo, magnitudes


def _unir_extras(extras: list[Prueba]) -> Prueba:
    todas_ok = all(e.estado == "OK" for e in extras)
    conjunto = Prueba(
        "extra", "Validaciones adicionales (rango, todo o nada, sensor ajeno, timestamp futuro)",
        "extra_validaciones_adicionales.md",
        ["`app/services/ingesta.py` → `procesar_mensaje` (pasos 3, 4 y 5)"],
        "Reglas que van más allá de la lista mínima de la guía: el valor debe estar dentro de "
        "`valor_minimo`/`valor_maximo`; si una magnitud es inválida no se guarda ninguna del mismo "
        "payload; solo se almacenan datos del sensor asignado (no se tocan datos de otros grupos); y "
        "un timestamp futuro se considera inválido.",
    )
    conjunto.estado = "OK" if todas_ok else "FALLO"
    conjunto.entrada = "Cuatro mensajes inválidos adicionales (detallados abajo)."
    conjunto.resultado = "\n\n".join(
        f"### {e.numero}. {e.titulo} — {e.estado}\n\n{e.entrada}\n\n{e.resultado}" for e in extras
    )
    conjunto.registro = "\n\n".join(f"**{e.numero}.** {e.registro}" for e in extras)
    return conjunto


# ======================================================================================
# Pruebas 8 a 16 — API HTTP
# ======================================================================================
def pruebas_http(ctx: Contexto, db: Session, cliente, modo: str) -> list[Prueba]:
    pruebas: list[Prueba] = []
    sid = ctx.sensor_id
    nota_modo = f"Las consultas se ejecutaron contra {modo}."

    def nueva(num, titulo, archivo, impl, expl):
        p = Prueba(num, titulo, archivo, impl, expl)
        p.registro = "No aplica: consulta de solo lectura (GET)."
        p.notas.append(nota_modo)
        return p

    # Datos de referencia ------------------------------------------------------------
    if ctx.total == 0:
        for num, titulo, archivo in [
            ("8", "Consulta por ID existente", "08_consulta_por_id_existente.md"),
            ("9", "Consulta por ID inexistente", "09_consulta_por_id_inexistente_404.md"),
            ("10", "Consulta histórica", "10_consulta_historica.md"),
            ("11", "Consulta por rango de fechas", "11_consulta_por_rango_de_fechas.md"),
            ("12", "Rango desde > hasta", "12_rango_invalido_400.md"),
            ("13", "Validación HTTP incorrecta", "13_validacion_http_422.md"),
            ("14", "Última medición", "14_ultima_medicion.md"),
            ("15", "Últimas N mediciones", "15_ultimas_n_mediciones.md"),
            ("16", "Filtro por magnitud", "16_filtro_por_magnitud.md"),
        ]:
            pruebas.append(sin_datos(nueva(num, titulo, archivo, [], "-"), "Aún no hay mediciones del sensor."))
        return pruebas

    ultimo_id, ultima_mag, ultimo_ts = ctx.filas[0]

    # 8 ---------------------------------------------------------------------------------
    p = nueva("8", "Consulta por ID existente", "08_consulta_por_id_existente.md",
              ["`app/api/medicion.py` → `obtener_medicion`", "`app/crud/medicion.py` → `obtener`",
               "`app/schemas/medicion.py` → `MedicionOut.desde_orm` (conversión a hora de Colombia)"],
              "Se consulta una medición real por su `id`. La respuesta incluye la magnitud, la unidad y el sensor "
              "(por las claves foráneas) y muestra el instante en hora de Colombia, aunque en la base se guarda en UTC.")
    r = llamar(cliente, f"/mediciones/{ultimo_id}")
    esperado_local = formatear_local(ultimo_ts)
    ok = r["estado"] == 200 and r["cuerpo"].get("id") == ultimo_id and r["cuerpo"].get("timestamp_local") == esperado_local \
        and r["cuerpo"].get("sensor_codigo") == ctx.codigo
    p.entrada = f"Medición existente con id `{ultimo_id}` (la más reciente del sensor `{ctx.codigo}`)."
    p.resultado = (bloque_http(r) + f"\n\nConversión verificada: en la base `timestamp_utc` = `{ultimo_ts.isoformat()}`; "
                   f"la respuesta muestra `{esperado_local}` (UTC-05:00).")
    p.http = "**200 OK**"
    p.estado = "OK" if ok else "FALLO"
    pruebas.append(p)

    # 9 ---------------------------------------------------------------------------------
    inexistente = ctx.filas[0][0] + 1_000_000
    p = nueva("9", "Consulta por ID inexistente", "09_consulta_por_id_inexistente_404.md",
              ["`app/api/medicion.py` → `obtener_medicion` (lanza `HTTPException(404)` si `crud.obtener` devuelve `None`)"],
              "Un `id` con formato válido pero que no existe responde 404 con un mensaje claro.")
    r = llamar(cliente, f"/mediciones/{inexistente}")
    p.entrada = f"`id` inexistente: `{inexistente}`."
    p.resultado = bloque_http(r)
    p.http = "**404 Not Found**"
    p.estado = "OK" if r["estado"] == 404 else "FALLO"
    pruebas.append(p)

    # 10 --------------------------------------------------------------------------------
    p = nueva("10", "Consulta histórica", "10_consulta_historica.md",
              ["`app/api/medicion.py` → `listar_mediciones_del_sensor`", "`app/crud/medicion.py` → `listar_por_sensor`"],
              "Sin filtros devuelve todo el histórico del sensor, de la medición más reciente a la más antigua.")
    antes = total_actual(db, ctx)
    r = llamar(cliente, f"/sensores/{sid}/mediciones")
    despues = total_actual(db, ctx)
    cuerpo = r["cuerpo"] if isinstance(r["cuerpo"], list) else []
    marcas = [c["timestamp_local"] for c in cuerpo]
    ok = r["estado"] == 200 and antes <= len(cuerpo) <= despues and marcas == sorted(marcas, reverse=True)
    p.entrada = f"Todas las mediciones del sensor con id `{sid}` (`{ctx.codigo}`)."
    p.resultado = (bloque_http(r) + f"\n\nFilas devueltas: **{len(cuerpo)}** (en la base: {antes}). "
                   "Ordenadas de la más reciente a la más antigua.")
    p.http = "**200 OK**"
    p.estado = "OK" if ok else "FALLO"
    pruebas.append(p)

    # 11 y 12 ----------------------------------------------------------------------------
    p11 = nueva("11", "Consulta por rango de fechas", "11_consulta_por_rango_de_fechas.md",
                ["`app/api/medicion.py` → `listar_mediciones_del_sensor` / `_fecha_o_422`",
                 "`app/core/tiempo.py` → `parsear_filtro_fecha`", "`app/crud/medicion.py` → `listar_por_sensor` (filtros `desde`/`hasta`)"],
                "`desde` y `hasta` son inclusivos. Con zona horaria (`Z` o `-05:00`) se respetan; sin zona se interpretan "
                "como hora de Colombia; solo con fecha abarcan el día completo.")
    p12 = nueva("12", "Rango con desde > hasta", "12_rango_invalido_400.md",
                ["`app/api/medicion.py` → `listar_mediciones_del_sensor` (lanza `HTTPException(400)`)"],
                "Si `desde` es posterior a `hasta` la consulta es contradictoria y se responde 400 antes de consultar la base.")
    span = (ctx.t_max - ctx.t_min).total_seconds()
    if len(ctx.filas) < 4 or span < 4:
        pruebas.append(sin_datos(p11, "No hay suficientes mediciones distribuidas en el tiempo para elegir un rango."))
        pruebas.append(sin_datos(p12, "No hay suficientes mediciones para elegir un rango."))
    else:
        d = ctx.t_min + timedelta(seconds=span * 0.25)
        h = ctx.t_min + timedelta(seconds=span * 0.75)
        d, h = parsear_timestamp_mqtt(iso_z(d)), parsear_timestamp_mqtt(iso_z(h))
        esperadas = [f for f in ctx.filas if d <= f[2] <= h]
        r = llamar(cliente, f"/sensores/{sid}/mediciones", desde=iso_z(d), hasta=iso_z(h))
        cuerpo = r["cuerpo"] if isinstance(r["cuerpo"], list) else []
        dentro = all(d <= a_utc(datetime.fromisoformat(c["timestamp_local"])) <= h for c in cuerpo)
        ok = r["estado"] == 200 and len(cuerpo) == len(esperadas) and dentro
        p11.entrada = (f"`desde={iso_z(d)}` y `hasta={iso_z(h)}` (UTC), que equivalen a "
                       f"{formatear_local(d)} y {formatear_local(h)} en Colombia.")
        p11.resultado = (bloque_http(r) + f"\n\nFilas devueltas: **{len(cuerpo)}**; esperadas según la base: "
                         f"**{len(esperadas)}** (del total de {len(ctx.filas)}). Todas dentro del rango: **{'sí' if dentro else 'no'}**.")
        p11.http = "**200 OK**"
        p11.estado = "OK" if ok else "FALLO"
        pruebas.append(p11)

        r = llamar(cliente, f"/sensores/{sid}/mediciones", desde=iso_z(h), hasta=iso_z(d))
        p12.entrada = f"`desde={iso_z(h)}` es posterior a `hasta={iso_z(d)}`."
        p12.resultado = bloque_http(r)
        p12.http = "**400 Bad Request**"
        p12.estado = "OK" if r["estado"] == 400 else "FALLO"
        pruebas.append(p12)

    # 13 --------------------------------------------------------------------------------
    p = nueva("13", "Validación HTTP incorrecta", "13_validacion_http_422.md",
              ["`app/api/dependencias.py` → `IdSensor` / `IdMedicion` (tipos de las rutas validados por FastAPI/Pydantic)",
               "`app/api/medicion.py` → `Query(ge=1)` en `limit` y `_fecha_o_422` para `desde`/`hasta`"],
              "FastAPI valida automáticamente los parámetros según su tipo y restricciones y responde 422 con el detalle del error.")
    casos = [
        llamar(cliente, "/sensores/abc"),
        llamar(cliente, f"/sensores/{sid}/mediciones", limit=0),
        llamar(cliente, f"/sensores/{sid}/mediciones", desde="no-es-una-fecha"),
    ]
    p.entrada = "Tres solicitudes con parámetros inválidos: id no numérico, `limit=0` y `desde` que no es fecha."
    p.resultado = "\n\n".join(f"### Caso {i}\n\n{bloque_http(c)}" for i, c in enumerate(casos, 1))
    p.http = "**422 Unprocessable Entity** (en los tres casos)"
    p.estado = "OK" if all(c["estado"] == 422 for c in casos) else "FALLO"
    pruebas.append(p)

    # 14 --------------------------------------------------------------------------------
    p = nueva("14", "Última medición", "14_ultima_medicion.md",
              ["`app/api/medicion.py` → `obtener_ultima_medicion`", "`app/crud/medicion.py` → `ultima_por_sensor`"],
              "Devuelve el registro con el `timestamp_utc` más reciente del sensor (desempata por `id`). "
              "Con `?magnitud=` devuelve la última de esa magnitud.")
    r = llamar(cliente, f"/sensores/{sid}/ultima-medicion")
    esperado_local = formatear_local(ultimo_ts)
    ok = r["estado"] == 200 and r["cuerpo"].get("timestamp_local", "") >= esperado_local
    r2 = llamar(cliente, f"/sensores/{sid}/ultima-medicion", magnitud=ultima_mag)
    ok = ok and r2["estado"] == 200 and r2["cuerpo"].get("magnitud") == ultima_mag
    p.entrada = f"Sensor `{ctx.codigo}`. En la base la medición más reciente es la `{ultimo_id}` ({ultimo_ts.isoformat()} UTC)."
    p.resultado = bloque_http(r) + "\n\nVariante por magnitud:\n\n" + bloque_http(r2)
    p.http = "**200 OK**"
    p.estado = "OK" if ok else "FALLO"
    pruebas.append(p)

    # 15 --------------------------------------------------------------------------------
    n = min(5, len(ctx.filas))
    p = nueva("15", "Últimas N mediciones (limit)", "15_ultimas_n_mediciones.md",
              ["`app/api/medicion.py` → `listar_mediciones_del_sensor` (parámetro `limit`)",
               "`app/crud/medicion.py` → `listar_por_sensor` (`ORDER BY timestamp_utc DESC ... LIMIT n`)"],
              "`limit=N` devuelve únicamente las N mediciones más recientes (cada fila es una magnitud de un mensaje).")
    r = llamar(cliente, f"/sensores/{sid}/mediciones", limit=n)
    cuerpo = r["cuerpo"] if isinstance(r["cuerpo"], list) else []
    marcas = [c["timestamp_local"] for c in cuerpo]
    quinto = formatear_local(ctx.filas[n - 1][2])
    ok = r["estado"] == 200 and len(cuerpo) == n and marcas == sorted(marcas, reverse=True) and min(marcas) >= quinto
    p.entrada = f"`limit={n}` sobre el sensor `{ctx.codigo}`."
    p.resultado = (bloque_http(r, maximo=n) + f"\n\nFilas devueltas: **{len(cuerpo)}**, de la más reciente a la más antigua.")
    p.http = "**200 OK**"
    p.estado = "OK" if ok else "FALLO"
    pruebas.append(p)

    # 16 --------------------------------------------------------------------------------
    magnitud = Counter(m for _, m, _ in ctx.filas).most_common(1)[0][0]
    p = nueva("16", "Filtro por magnitud", "16_filtro_por_magnitud.md",
              ["`app/api/medicion.py` → `listar_mediciones_del_sensor` (parámetro `magnitud`)",
               "`app/crud/medicion.py` → `listar_por_sensor` (JOIN con `sensor_magnitudes`)"],
              "El filtro se resuelve con un JOIN a `sensor_magnitudes`. Una magnitud que el sensor no tiene responde 404.")
    antes = sum(1 for _, m, _ in ctx.filas if m == magnitud)
    r = llamar(cliente, f"/sensores/{sid}/mediciones", magnitud=magnitud)
    cuerpo = r["cuerpo"] if isinstance(r["cuerpo"], list) else []
    ok = r["estado"] == 200 and len(cuerpo) >= antes and all(c["magnitud"] == magnitud for c in cuerpo)
    r2 = llamar(cliente, f"/sensores/{sid}/mediciones", magnitud="magnitud_inexistente")
    ok = ok and r2["estado"] == 404
    p.entrada = f"`magnitud={magnitud}` sobre el sensor `{ctx.codigo}`."
    p.resultado = (bloque_http(r) + f"\n\nFilas devueltas: **{len(cuerpo)}**, todas con `magnitud = {magnitud}` "
                   f"(en la base había {antes} al iniciar).\n\nMagnitud que el sensor no tiene:\n\n" + bloque_http(r2))
    p.http = "**200 OK** (filtro válido) y **404** (magnitud inexistente)"
    p.estado = "OK" if ok else "FALLO"
    pruebas.append(p)
    return pruebas

def prueba_17(ctx: Contexto) -> Prueba:
    p = Prueba(
        "17", "Claves foráneas", "17_claves_foraneas.md",
        ["`app/models/sensor_magnitud.py` → `SensorMagnitud.sensor_id` (`ForeignKey('sensores.id')`)",
         "`app/models/medicion.py` → `Medicion.sensor_magnitud_id` (`ForeignKey('sensor_magnitudes.id')`)",
         "`app/models/*.py` → `relationship()` entre las tres entidades"],
        "El modelo ORM reproduce las dos relaciones 1:N de `data-model.md`. PostgreSQL las hace cumplir "
        "(`ON UPDATE CASCADE ON DELETE RESTRICT`): no se puede insertar una medición de una magnitud "
        "inexistente ni borrar una magnitud con histórico.",
    )
    p.http = "No aplica: verificación del esquema y de las relaciones en la base de datos."
    insp = inspect(get_engine())
    fks = {
        t: [
            dict(nombre=f.get("name"), columnas=f["constrained_columns"], referencia=f"{f['referred_table']}({', '.join(f['referred_columns'])})",
                 opciones=f.get("options", {}))
            for f in insp.get_foreign_keys(t)
        ]
        for t in ("sensor_magnitudes", "mediciones")
    }
    p.entrada = "Inspección del esquema real de PostgreSQL y una inserción deliberadamente errónea (dentro de una transacción que se revierte)."

    with sesion_revertible() as sesion:
        huerfanas = sesion.execute(
            select(func.count()).select_from(Medicion)
            .outerjoin(SensorMagnitud, SensorMagnitud.id == Medicion.sensor_magnitud_id)
            .where(SensorMagnitud.id.is_(None))
        ).scalar()
        muestra = sesion.scalars(
            select(Medicion).where(Medicion.sensor_magnitud_id.in_(ctx.ids_magnitud))
            .order_by(Medicion.timestamp_utc.desc(), Medicion.id.desc()).limit(1)
        ).first()
        recorrido = (
            f"medición {muestra.id} -> sensor_magnitud {muestra.sensor_magnitud.id} ({muestra.sensor_magnitud.magnitud}, "
            f"{muestra.sensor_magnitud.unidad}) -> sensor {muestra.sensor_magnitud.sensor.id} ({muestra.sensor_magnitud.sensor.codigo})"
            if muestra else "(sin mediciones todavía)"
        )
        try:
            with sesion.begin_nested():
                sesion.add(Medicion(id=-1, sensor_magnitud_id=2_000_000_000, valor=Decimal("1"), timestamp_utc=ahora_utc()))
                sesion.flush()
            violacion, rechazada = "La base de datos aceptó una medición huérfana (INCORRECTO).", False
        except DBAPIError as exc:
            violacion = describir_error(exc)
            rechazada = codigo_sqlstate(exc) == "23503" or "foreign key" in violacion.lower()

    p.resultado = (
        f"Claves foráneas definidas en PostgreSQL:\n\n{json_md(fks)}\n\n"
        f"Recorrido por el ORM (relationships):\n\n{texto_md(recorrido)}\n\n"
        f"Mediciones huérfanas (sin magnitud asociada): **{huerfanas}**\n\n"
        f"Intento de insertar una medición con `sensor_magnitud_id = 2000000000` (no existe):\n\n{texto_md(violacion)}"
    )
    p.registro = "RECHAZADO por la base de datos (violación de clave foránea); la transacción se revirtió, no queda nada guardado."
    p.estado = "OK" if (rechazada and huerfanas == 0 and fks["mediciones"] and fks["sensor_magnitudes"]) else "FALLO"
    return p


ESTRUCTURA = [
    ("app/main.py", "Punto de entrada: crea la app FastAPI, registra los routers y arranca/detiene el consumidor MQTT (lifespan)."),
    ("app/database/connection.py", "Engine, sesiones y clase base del ORM; dependencia `get_db`."),
    ("app/models/sensor.py", "Tabla `sensores` como clase ORM."),
    ("app/models/sensor_magnitud.py", "Tabla `sensor_magnitudes` (FK a sensores)."),
    ("app/models/medicion.py", "Tabla `mediciones` (FK a sensor_magnitudes)."),
    ("app/schemas/sensor.py", "Esquema Pydantic de respuesta de sensores."),
    ("app/schemas/sensor_magnitud.py", "Esquema Pydantic de respuesta de sensor-magnitudes."),
    ("app/schemas/medicion.py", "Esquemas Pydantic del payload MQTT (validación) y de la respuesta de mediciones."),
    ("app/crud/sensor.py", "Consultas de sensores (solo lectura)."),
    ("app/crud/sensor_magnitud.py", "Consultas de sensor-magnitudes (solo lectura)."),
    ("app/crud/medicion.py", "Inserción atómica y consultas de mediciones."),
    ("app/services/ingesta.py", "Reglas de negocio de la ingesta MQTT (validación en capas y almacenamiento)."),
    ("app/api/sensor.py", "Endpoints HTTP de sensores."),
    ("app/api/sensor_magnitud.py", "Endpoints HTTP de sensor-magnitudes."),
    ("app/api/medicion.py", "Endpoints HTTP de mediciones."),
    ("app/mqtt/client.py", "Transporte MQTT: conexión, suscripción, reconexión y registro; delega en el servicio."),
    ("app/core/config.py", "Variables de entorno."),
    ("app/core/tiempo.py", "UTC <-> hora de Colombia y parseo de fechas."),
]

# (carpeta, patrón prohibido, descripción de la regla)
REGLAS = [
    ("app/api", r"\bselect\(|\.execute\(|\.add\(|\.commit\(", "las rutas HTTP no escriben SQL: delegan en `crud/`"),
    ("app/mqtt", r"\bselect\(|\.execute\(|\.add\(|\.commit\(|from app\.models", "el cliente MQTT no accede a la base: delega en `services/`"),
    ("app/crud", r"fastapi|HTTPException|paho", "`crud/` no conoce HTTP ni MQTT"),
    ("app/models", r"fastapi|pydantic|paho|from app\.crud", "`models/` solo describe tablas"),
    ("app/schemas", r"\.execute\(|\.commit\(|paho|from app\.crud", "`schemas/` solo valida/serializa datos"),
]


def prueba_18() -> Prueba:
    p = Prueba(
        "18", "Separación de responsabilidades", "18_separacion_de_responsabilidades.md",
        ["Estructura `app/` completa (ver tabla)", "`app/services/ingesta.py` (lógica de negocio separada del transporte MQTT y de HTTP)"],
        "Cada capa tiene una única responsabilidad y solo conoce a la inferior: `api`/`mqtt` -> `services`/`crud` -> `models`/`database`. "
        "Los esquemas Pydantic validan datos de entrada/salida y no tocan la base.",
    )
    filas, faltan = [], 0
    for ruta, descripcion in ESTRUCTURA:
        existe = (RAIZ / ruta).exists()
        faltan += 0 if existe else 1
        filas.append(f"| `{ruta}` | {'sí' if existe else '**NO**'} | {descripcion} |")

    reglas, violaciones = [], 0
    for carpeta, patron, texto in REGLAS:
        malos = []
        for archivo in sorted((RAIZ / carpeta).glob("*.py")):
            codigo = "\n".join(l for l in archivo.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
            if re.search(patron, codigo):
                malos.append(archivo.name)
        violaciones += len(malos)
        reglas.append(f"| `{carpeta}/` | {texto} | {'cumple' if not malos else 'INCUMPLE: ' + ', '.join(malos)} |")

    p.entrada = "Revisión automática del código fuente de `app/` (existencia de archivos y reglas entre capas)."
    p.resultado = (
        "| Archivo | Existe | Responsabilidad |\n|---|---|---|\n" + "\n".join(filas) +
        "\n\nReglas de dependencia entre capas (búsqueda de patrones prohibidos en el código):\n\n"
        "| Carpeta | Regla | Resultado |\n|---|---|---|\n" + "\n".join(reglas)
    )
    p.registro = "No aplica."
    p.http = "No aplica."
    p.estado = "OK" if faltan == 0 and violaciones == 0 else "FALLO"
    return p

def escribir_resumen(ctx: Contexto, pruebas: list[Prueba]) -> None:
    orden = sorted(
        pruebas,
        key=lambda p: (int(p.numero) if p.numero.isdigit() else 99, p.numero),
    )
    filas = "\n".join(
        f"| {p.numero} | {p.titulo} | {p.estado} | [{p.archivo}]({p.archivo}) |" for p in orden
    )
    captura = (
        f"tramo continuo de {ctx.minutos_continuos:.1f} min ({'cumple' if ctx.minutos_continuos >= 20 else 'NO cumple'} "
        f"el mínimo de 20 min); entre la primera y la última medición: {ctx.minutos:.1f} min"
        if ctx.total else "sin datos"
    )
    contenido = f"""# Resumen de evidencias

**Generado:** {hora_local()} (hora de Colombia) con `python -m scripts.generar_evidencias`

| Dato | Valor |
|---|---|
| Sensor asignado | `{ctx.codigo}` (id {ctx.sensor_id}) |
| Tópico MQTT | `{ctx.topico}` |
| Filas almacenadas en `mediciones` (una por magnitud) | {ctx.total} |
| Ventana de captura | {captura} |

Archivos de apoyo: [00_catalogo_sensor.md](00_catalogo_sensor.md) (conexión a PostgreSQL y catálogo del sensor) y
[00_captura_mqtt_inicial.md](00_captura_mqtt_inicial.md) (mensajes reales recibidos y estructura del payload).
Registro de ejecución de la aplicación (consumidor MQTT): [registro_ejecucion.txt](registro_ejecucion.txt).

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
{filas}

Cada archivo indica: datos de entrada, resultado obtenido, código HTTP, registro almacenado o rechazado,
archivo y función donde se implementa la lógica, y una breve explicación.
"""
    (EVIDENCIAS / "resumen.md").write_text(contenido, encoding="utf-8")


def main() -> int:
    consola_utf8()
    parser = argparse.ArgumentParser(description="Genera las evidencias de las 18 pruebas.")
    parser.add_argument("--url", help="URL del servidor en ejecución (por defecto, TestClient en proceso)")
    args = parser.parse_args()

    try:
        settings = get_settings()
        settings.validar_mqtt()
        with get_session_factory()() as db:
            ctx = cargar_contexto(db, settings.mqtt_topic)
    except ConfiguracionError as exc:
        print(f"Configuración incompleta: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer la base de datos: {describir_error(exc)}")
        if pista := pista_error_bd(exc):
            print(f"Sugerencia: {pista}")
        return 2

    print(f"Sensor {ctx.codigo} | {ctx.total} filas | tramo continuo de captura: {ctx.minutos_continuos:.1f} min "
          f"(primera a última: {ctx.minutos:.1f} min)")
    EVIDENCIAS.mkdir(exist_ok=True)
    log = analizar_log()
    incluidas = guardar_extracto_log()
    if incluidas:
        print(f"  Extracto del registro de ejecución: evidencias/registro_ejecucion.txt ({incluidas} líneas)")
    cliente, modo = crear_cliente(args.url)

    pruebas: list[Prueba] = []
    with get_session_factory()() as db:
        generadores = [
            lambda: [prueba_1(ctx, log)],
            lambda: [prueba_2(ctx, db, log)],
            lambda: pruebas_de_rechazo(ctx, log),
            lambda: pruebas_http(ctx, db, cliente, modo),
            lambda: [prueba_17(ctx)],
            lambda: [prueba_18()],
        ]
        for generar in generadores:
            try:
                nuevas = generar()
            except Exception:  # noqa: BLE001 - una falla no debe impedir generar el resto
                print("  [ERROR] " + traceback.format_exc().strip().splitlines()[-1])
                continue
            for prueba in nuevas:
                prueba.guardar()
            pruebas.extend(nuevas)

    escribir_resumen(ctx, pruebas)
    por_estado = Counter(p.estado for p in pruebas)
    print("\nResumen:", ", ".join(f"{k}={v}" for k, v in sorted(por_estado.items())))
    print("Evidencias en la carpeta evidencias/ (empieza por resumen.md)")
    return 0 if por_estado.get("FALLO", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
