"""Consumidor MQTT (`app/mqtt/client.py`): callbacks, robustez y configuración."""

import json
import logging
from types import SimpleNamespace

import paho.mqtt.client as paho
import pytest
from sqlalchemy import select

from app.core import config
from app.core.config import ConfiguracionError, Settings
from app.models import Medicion
from app.mqtt.client import ClienteMQTT

from .conftest import TOPICO, payload, total_mediciones


def configuracion(**cambios) -> Settings:
    base = dict(
        db_host=None, db_port=5432, db_name=None, db_user=None, db_password=None,
        database_url_env=None, mqtt_enabled=True, mqtt_broker="localhost", mqtt_port=1883,
        mqtt_topic=TOPICO, mqtt_username=None, mqtt_password=None, mqtt_keepalive=60,
        log_level="INFO", tolerancia_futuro_segundos=600,
    )
    base.update(cambios)
    return Settings(**base)


def mensaje(contenido, topico: str = TOPICO):
    crudo = contenido if isinstance(contenido, bytes) else json.dumps(contenido).encode()
    return SimpleNamespace(topic=topico, payload=crudo)


@pytest.fixture
def cliente(fabrica):
    return ClienteMQTT(configuracion(), fabrica_sesiones=fabrica)


def test_mensaje_valido_se_almacena_y_se_registra(cliente, db, caplog):
    with caplog.at_level(logging.INFO, logger="app"):
        cliente._al_recibir(None, None, mensaje(payload()))

    assert (cliente.recibidos, cliente.almacenados, cliente.rechazados) == (1, 1, 0)
    assert total_mediciones(db) == 1
    textos = [r.getMessage() for r in caplog.records]
    assert any(t.startswith("MENSAJE RECIBIDO") and TOPICO in t for t in textos)
    assert any(t.startswith("ALMACENADO | sensor=GAS-004") for t in textos)


def test_mensaje_invalido_se_rechaza_y_se_registra(cliente, db, caplog):
    with caplog.at_level(logging.INFO, logger="app"):
        cliente._al_recibir(None, None, mensaje(payload(sensor_id="XYZ-000")))

    assert (cliente.recibidos, cliente.almacenados, cliente.rechazados) == (1, 0, 1)
    assert total_mediciones(db) == 0
    assert any("RECHAZADO | motivo=SENSOR_INEXISTENTE" in r.getMessage() for r in caplog.records)


def test_un_error_inesperado_no_detiene_el_consumidor(cliente, db, monkeypatch, caplog):
    def explota(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr("app.mqtt.client.procesar_mensaje", explota)
    with caplog.at_level(logging.INFO, logger="app"):
        cliente._al_recibir(None, None, mensaje(payload()))  # no debe propagar la excepción
    assert cliente.rechazados == 1

    monkeypatch.undo()
    cliente._al_recibir(None, None, mensaje(payload()))  # el siguiente mensaje sí se procesa
    assert cliente.almacenados == 1 and total_mediciones(db) == 1


def test_basura_binaria_no_rompe_el_consumidor(cliente, db):
    cliente._al_recibir(None, None, mensaje(b"\x00\xff\xfe"))
    cliente._al_recibir(None, None, mensaje(b""))
    cliente._al_recibir(None, None, mensaje(b"{"))
    assert cliente.rechazados == 3 and total_mediciones(db) == 0


def test_al_conectar_se_suscribe_al_topico_asignado(cliente):
    suscripciones = []

    class Falso:
        def subscribe(self, topico, qos=0):
            suscripciones.append((topico, qos))
            return paho.MQTT_ERR_SUCCESS, 1

    cliente._al_conectar(Falso(), None, None, paho.ReasonCode(paho.CONNACK >> 4, "Success"))
    assert cliente.conectado and suscripciones == [(TOPICO, 1)]


def test_conexion_rechazada_no_se_suscribe(cliente):
    class Falso:
        def subscribe(self, *args, **kwargs):
            raise AssertionError("no debe suscribirse")

    rechazo = paho.ReasonCode(paho.CONNACK >> 4, "Not authorized")
    cliente._al_conectar(Falso(), None, None, rechazo)
    assert not cliente.conectado


def test_estado_para_el_endpoint_de_salud(cliente):
    assert set(cliente.estado()) == {
        "conectado", "broker", "topico", "mensajes_recibidos", "mensajes_almacenados", "mensajes_rechazados",
    }


@pytest.mark.parametrize("topico", ["iot/sensors/+/data", "iot/sensors/#", "#"])
def test_no_se_permiten_comodines_en_el_topico(topico):
    with pytest.raises(ConfiguracionError, match="comodines"):
        ClienteMQTT(configuracion(mqtt_topic=topico))


def test_faltan_variables_mqtt():
    with pytest.raises(ConfiguracionError, match="MQTT_BROKER"):
        ClienteMQTT(configuracion(mqtt_broker=None))
    with pytest.raises(ConfiguracionError, match="MQTT_TOPIC"):
        ClienteMQTT(configuracion(mqtt_topic=None))


def test_url_de_base_de_datos_escapa_caracteres_especiales(monkeypatch):
    monkeypatch.setattr(config, "_motivo_no_disponible", lambda nombre: None)  # sin depender del controlador instalado
    url = configuracion(
        db_host="h", db_name="appdb", db_user="u", db_password="p@ss:/w#rd"
    ).database_url
    assert url.password == "p@ss:/w#rd"
    assert "p@ss:/w#rd" not in url.render_as_string(hide_password=True)


def test_faltan_variables_de_base_de_datos():
    with pytest.raises(ConfiguracionError, match="DB_HOST"):
        _ = configuracion().database_url


def test_mediciones_almacenadas_tienen_fecha_de_recepcion(cliente, db):
    cliente._al_recibir(None, None, mensaje(payload()))
    assert db.scalars(select(Medicion)).one().fecha_recepcion is not None
