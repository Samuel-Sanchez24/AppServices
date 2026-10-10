"""Consumidor MQTT.

Se conecta al broker, se suscribe **solo** al tópico del sensor asignado y entrega cada
mensaje a ``app.services.ingesta.procesar_mensaje``. Aquí no hay reglas de negocio: este
módulo solo se ocupa del transporte (conexión, suscripción, reconexión y registros).
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable

import paho.mqtt.client as paho
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.connection import get_session_factory
from app.services.ingesta import codigo_desde_topico, procesar_mensaje

logger = logging.getLogger("app.mqtt")

_LONGITUD_MAXIMA_LOG = 600


def _resumir_payload(payload: bytes) -> str:
    texto = payload.decode("utf-8", errors="replace")
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > _LONGITUD_MAXIMA_LOG:
        texto = texto[:_LONGITUD_MAXIMA_LOG] + "…"
    return texto


class ClienteMQTT:
    """Suscriptor MQTT que corre en un hilo propio (``loop_start``) y se reconecta solo."""

    def __init__(
        self,
        settings: Settings | None = None,
        fabrica_sesiones: Callable[[], Session] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._settings.validar_mqtt()
        self._fabrica_sesiones = fabrica_sesiones
        self._cliente: paho.Client | None = None

        self.topico: str = self._settings.mqtt_topic
        self.conectado = False
        self.recibidos = 0
        self.almacenados = 0
        self.rechazados = 0

    # -- ciclo de vida ----------------------------------------------------------------
    def iniciar(self) -> None:
        s = self._settings
        sufijo = codigo_desde_topico(self.topico) or "sensor"
        cliente = paho.Client(
            paho.CallbackAPIVersion.VERSION2,
            client_id=f"taller2-{sufijo}-{uuid.uuid4().hex[:8]}",  # único: el broker expulsa IDs repetidos
        )
        if s.mqtt_username:
            cliente.username_pw_set(s.mqtt_username, s.mqtt_password or "")

        cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        cliente.on_connect = self._al_conectar
        cliente.on_connect_fail = self._al_fallar_conexion
        cliente.on_disconnect = self._al_desconectar
        cliente.on_message = self._al_recibir
        self._cliente = cliente

        logger.info("Conectando al broker MQTT %s:%s ...", s.mqtt_broker, s.mqtt_port)
        # connect_async no bloquea ni falla si el broker aún no responde: el hilo de red reintenta.
        cliente.connect_async(s.mqtt_broker, s.mqtt_port, s.mqtt_keepalive)
        cliente.loop_start()

    def detener(self) -> None:
        if self._cliente is None:
            return
        self.conectado = False  # desconexión voluntaria: evita el aviso de «se reintentará»
        self._cliente.disconnect()
        self._cliente.loop_stop()
        self._cliente = None
        self.conectado = False
        logger.info("Consumidor MQTT detenido")

    def estado(self) -> dict[str, object]:
        return {
            "conectado": self.conectado,
            "broker": f"{self._settings.mqtt_broker}:{self._settings.mqtt_port}",
            "topico": self.topico,
            "mensajes_recibidos": self.recibidos,
            "mensajes_almacenados": self.almacenados,
            "mensajes_rechazados": self.rechazados,
        }

    # -- callbacks de paho (hilo de red) ------------------------------------------------
    def _al_conectar(self, cliente, userdata, flags, reason_code, properties=None) -> None:
        if reason_code.is_failure:
            self.conectado = False
            logger.error("El broker rechazó la conexión: %s", reason_code)
            return

        self.conectado = True
        logger.info(
            "Conectado al broker %s:%s", self._settings.mqtt_broker, self._settings.mqtt_port
        )
        # Se suscribe en cada (re)conexión porque la sesión es limpia (clean session).
        resultado, _ = cliente.subscribe(self.topico, qos=1)
        if resultado == paho.MQTT_ERR_SUCCESS:
            logger.info("Suscrito al tópico: %s", self.topico)
        else:
            logger.error("No fue posible suscribirse a %s (código %s)", self.topico, resultado)

    def _al_fallar_conexion(self, cliente, userdata) -> None:
        self.conectado = False
        logger.warning("No se pudo conectar al broker MQTT; se reintentará automáticamente")

    def _al_desconectar(
        self, cliente, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        if self.conectado:
            logger.warning("Desconectado del broker MQTT (%s); se reintentará", reason_code)
        self.conectado = False

    def _al_recibir(self, cliente, userdata, mensaje) -> None:
        """Un fallo al procesar un mensaje nunca debe detener el consumidor."""
        self.recibidos += 1
        logger.info(
            "MENSAJE RECIBIDO | topico=%s | payload=%s",
            mensaje.topic,
            _resumir_payload(mensaje.payload),
        )
        try:
            fabrica = self._fabrica_sesiones or get_session_factory()
            with fabrica() as db:
                resultado = procesar_mensaje(db, mensaje.topic, mensaje.payload)
        except Exception:  # noqa: BLE001 - se registra y se continúa con el siguiente mensaje
            self.rechazados += 1
            logger.exception("Error inesperado procesando el mensaje; se descarta")
            return

        if resultado.almacenado:
            self.almacenados += 1
            logger.info(resultado.resumen())
        else:
            self.rechazados += 1
            logger.warning(resultado.resumen())
