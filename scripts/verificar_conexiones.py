from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

import paho.mqtt.client as paho
from sqlalchemy import func, select, text

from app.core.config import ConfiguracionError, get_settings
from app.core.tiempo import ahora_utc, formatear_local
from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_engine, get_session_factory
from app.database.errores import describir_error, pista_error_bd
from app.models import Medicion, Sensor, SensorMagnitud
from app.services.ingesta import codigo_desde_topico, procesar_mensaje

EVIDENCIAS = Path(__file__).resolve().parents[1] / "evidencias"


def _hora_local() -> str:
    return formatear_local(ahora_utc()).replace("T", " ")


def _consola_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _guardar(nombre: str, contenido: str) -> None:
    EVIDENCIAS.mkdir(exist_ok=True)
    (EVIDENCIAS / nombre).write_text(contenido, encoding="utf-8")
    print(f"      -> evidencia guardada: evidencias/{nombre}")


# ---------------------------------------------------------------------------------------
def verificar_base_de_datos(codigo: str | None) -> bool:
    print("\n[1/2] PostgreSQL")
    try:
        driver = get_settings().driver_bd
        no_cargados = "".join(
            f" ({n} no se pudo cargar en este equipo: {m.split(':')[0]})" for n, m in driver.descartados
        )
        print(f"      Controlador: {driver.nombre}{no_cargados}")
        with get_engine().connect() as conexion:
            version = conexion.execute(text("SELECT version()")).scalar()
            base = conexion.execute(text("SELECT current_database()")).scalar()
        with get_session_factory()() as db:
            totales = {
                "sensores": db.scalar(select(func.count()).select_from(Sensor)),
                "sensor_magnitudes": db.scalar(select(func.count()).select_from(SensorMagnitud)),
                "mediciones": db.scalar(select(func.count()).select_from(Medicion)),
            }
            sensor = crud_sensor.obtener_por_codigo(db, codigo) if codigo else None
            magnitudes = crud_sensor_magnitud.listar_por_sensor(db, sensor.id) if sensor else []
            sensor_datos = (
                dict(id=sensor.id, codigo=sensor.codigo, nombre=sensor.nombre,
                     categoria=sensor.categoria, ubicacion=sensor.ubicacion, activo=sensor.activo)
                if sensor else None
            )
            catalogo = [
                (m.id, m.magnitud, m.unidad, float(m.valor_minimo), float(m.valor_maximo))
                for m in magnitudes
            ]
    except Exception as exc:  # noqa: BLE001 - se informa y se sigue con MQTT
        print(f"      ERROR de conexión a PostgreSQL: {describir_error(exc)}")
        if pista := pista_error_bd(exc):
            print(f"      Sugerencia: {pista}")
        return False

    print(f"      Conectado a la base '{base}'. {version.split(',')[0]}")
    print("      Filas: " + ", ".join(f"{k}={v}" for k, v in totales.items()))
    if sensor_datos is None:
        print(f"      ATENCION: el sensor '{codigo}' no existe en la tabla sensores.")
        return False

    print(f"      Sensor asignado: {sensor_datos}")
    for _, nombre, unidad, minimo, maximo in catalogo:
        print(f"        - {nombre}: unidad '{unidad}', rango [{minimo}, {maximo}]")

    filas = "\n".join(
        f"| {i} | `{n}` | `{u}` | {lo} | {hi} |" for i, n, u, lo, hi in catalogo
    )
    _guardar(
        "00_catalogo_sensor.md",
        f"""# 00 — Conexión a PostgreSQL y catálogo del sensor asignado

**Generado:** {_hora_local()} (hora de Colombia) con `python -m scripts.verificar_conexiones`

## Conexión
- Base de datos: `{base}` (el host y las credenciales se leen de `.env` y no se publican).
- Servidor: {version.split(',')[0]}
- Filas actuales: {', '.join(f'`{k}` = {v}' for k, v in totales.items())}

## Sensor asignado
| id | codigo | nombre | categoria | ubicacion | activo |
|---|---|---|---|---|---|
| {sensor_datos['id']} | `{sensor_datos['codigo']}` | {sensor_datos['nombre']} | {sensor_datos['categoria']} | {sensor_datos['ubicacion']} | {sensor_datos['activo']} |

## Magnitudes configuradas (`sensor_magnitudes`)
| id | magnitud | unidad | valor_minimo | valor_maximo |
|---|---|---|---|---|
{filas}

Estas magnitudes, unidades y rangos son los que valida la aplicación al recibir cada mensaje.
""",
    )
    return True


# ---------------------------------------------------------------------------------------
def _escuchar(broker: str, puerto: int, topico: str, keepalive: int, segundos: int, maximo: int):
    recibidos: list[tuple[str, str, bytes]] = []
    listo = threading.Event()
    estado: dict[str, str | None] = {"error": None}

    def al_conectar(cliente, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            estado["error"] = f"el broker rechazó la conexión: {reason_code}"
            listo.set()
            return
        print(f"      Conectado a {broker}:{puerto}. Suscrito a '{topico}'. Esperando mensajes...")
        cliente.subscribe(topico, qos=1)

    def al_recibir(cliente, userdata, mensaje):
        recibidos.append((_hora_local(), mensaje.topic, bytes(mensaje.payload)))
        resumen = " ".join(mensaje.payload.decode("utf-8", errors="replace").split())
        print(f"      [{len(recibidos)}/{maximo}] {resumen[:160]}")
        if len(recibidos) >= maximo:
            listo.set()

    cliente = paho.Client(
        paho.CallbackAPIVersion.VERSION2, client_id=f"verificacion-{uuid.uuid4().hex[:8]}"
    )
    cliente.on_connect = al_conectar
    cliente.on_message = al_recibir
    try:
        cliente.connect(broker, puerto, keepalive)
    except Exception as exc:  # noqa: BLE001
        print(f"      ERROR de conexión al broker MQTT: {exc.__class__.__name__}: {exc}")
        return None

    cliente.loop_start()
    inicio = time.monotonic()
    while not listo.wait(0.5) and time.monotonic() - inicio < segundos:
        pass
    cliente.loop_stop()
    cliente.disconnect()

    if estado["error"]:
        print(f"      ERROR: {estado['error']}")
        return None
    return recibidos


def verificar_mqtt(segundos: int, maximo: int, sesion_disponible: bool) -> bool:
    print("\n[2/2] MQTT")
    s = get_settings()
    print(f"      Broker {s.mqtt_broker}:{s.mqtt_port} | tópico {s.mqtt_topic} | hasta {segundos} s")
    recibidos = _escuchar(
        s.mqtt_broker, s.mqtt_port, s.mqtt_topic, s.mqtt_keepalive, segundos, maximo
    )
    if recibidos is None:
        return False
    if not recibidos:
        print(
            f"      No llegó ningún mensaje en {segundos} s. Revisa el tópico asignado o "
            "aumenta --segundos."
        )
        return False

    secciones: list[str] = []
    observado: dict[str, dict[str, set]] = defaultdict(lambda: {"unidades": set(), "tipos": set(), "valores": set()})
    formatos_timestamp: set[str] = set()

    sesion = get_session_factory()() if sesion_disponible else None
    try:
        for n, (hora, topico, crudo) in enumerate(recibidos, 1):
            texto = crudo.decode("utf-8", errors="replace")
            try:
                datos = json.loads(texto)
                bonito = json.dumps(datos, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                datos, bonito = None, texto

            if isinstance(datos, dict):
                if isinstance(datos.get("timestamp"), str):
                    formatos_timestamp.add(datos["timestamp"])
                medidas = datos.get("measurements")
                if isinstance(medidas, dict):
                    for nombre, item in medidas.items():
                        if isinstance(item, dict):
                            observado[nombre]["unidades"].add(repr(item.get("unit")))
                            observado[nombre]["tipos"].add(type(item.get("value")).__name__)
                            if isinstance(item.get("value"), (int, float)) and not isinstance(item.get("value"), bool):
                                observado[nombre]["valores"].add(item["value"])

            if sesion is not None:
                veredicto = procesar_mensaje(sesion, topico, crudo, guardar=False).resumen()
            else:
                veredicto = "(sin conexión a la base de datos: no se pudo validar)"
            print(f"      Mensaje {n}: {veredicto[:200]}")

            secciones.append(
                f"### Mensaje {n}\n\n- Recibido: {hora} (hora de Colombia)\n- Tópico: `{topico}`\n\n"
                f"```json\n{bonito}\n```\n\n"
                f"Resultado de validarlo (simulación, sin escribir en la base): `{veredicto}`\n"
            )
    finally:
        if sesion is not None:
            sesion.close()

    filas = "\n".join(
        f"| `{nombre}` | {', '.join(sorted(info['unidades']))} | {', '.join(sorted(info['tipos']))} "
        f"| {min(info['valores']) if info['valores'] else '-'} a {max(info['valores']) if info['valores'] else '-'} |"
        for nombre, info in sorted(observado.items())
    ) or "| (no se pudieron leer magnitudes) | | | |"
    ejemplos_ts = ", ".join(f"`{t}`" for t in sorted(formatos_timestamp)[:3]) or "-"

    _guardar(
        "00_captura_mqtt_inicial.md",
        f"""# 00 — Captura inicial de mensajes MQTT del tópico asignado

**Generado:** {_hora_local()} (hora de Colombia) con `python -m scripts.verificar_conexiones`

| Dato | Valor |
|---|---|
| Broker | `{get_settings().mqtt_broker}:{get_settings().mqtt_port}` |
| Tópico suscrito | `{get_settings().mqtt_topic}` |
| Mensajes capturados | {len(recibidos)} |

## Estructura observada del payload
- `sensor_id` (texto): código del sensor, corresponde a `sensores.codigo`.
- `timestamp` (texto ISO 8601 en UTC). Ejemplos recibidos: {ejemplos_ts}
- `measurements` (objeto): una clave por magnitud, cada una con `value` (número) y `unit` (texto).

## Magnitudes, unidades y tipos observados
| Magnitud | Unidad(es) | Tipo de `value` | Rango de valores observado |
|---|---|---|---|
{filas}

## Mensajes recibidos
{chr(10).join(secciones)}
**Implementación:** `app/mqtt/client.py` → `ClienteMQTT._al_conectar` (suscripción) y `ClienteMQTT._al_recibir` (recepción).
""",
    )
    return True


def main() -> int:
    _consola_utf8()
    parser = argparse.ArgumentParser(description="Verifica la conexión a PostgreSQL y MQTT.")
    parser.add_argument("--segundos", type=int, default=90, help="tiempo máximo de espera MQTT")
    parser.add_argument("--mensajes", type=int, default=5, help="mensajes a capturar")
    args = parser.parse_args()

    try:
        settings = get_settings()
        settings.validar_mqtt()
    except ConfiguracionError as exc:
        print(f"Configuración incompleta: {exc}")
        return 2

    codigo = codigo_desde_topico(settings.mqtt_topic)
    ok_bd = verificar_base_de_datos(codigo)
    ok_mqtt = verificar_mqtt(args.segundos, args.mensajes, sesion_disponible=ok_bd)

    print("\nResumen:", "PostgreSQL OK" if ok_bd else "PostgreSQL CON PROBLEMAS", "|",
          "MQTT OK" if ok_mqtt else "MQTT CON PROBLEMAS")
    return 0 if ok_bd and ok_mqtt else 1


if __name__ == "__main__":
    raise SystemExit(main())
