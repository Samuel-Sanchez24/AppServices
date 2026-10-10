"""Validación y almacenamiento de mensajes MQTT (`app/services/ingesta.py`).

Cada prueba corresponde a un caso de la guía: solo se almacenan los mensajes que superan
TODAS las validaciones, y los rechazados no dejan ningún registro.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models import Medicion
from app.services import ingesta
from app.services.ingesta import Motivo, codigo_desde_topico, procesar_mensaje

from .conftest import TOPICO, enviar, payload, total_mediciones


# -- caso válido --------------------------------------------------------------------------
def test_medicion_valida_se_almacena_en_utc(db):
    resultado = enviar(db, payload())

    assert resultado.almacenado
    assert resultado.motivo is None
    fila = db.scalars(select(Medicion)).one()
    assert fila.valor == Decimal("412.5")
    assert fila.sensor_magnitud.magnitud == "co2"
    assert fila.sensor_magnitud.sensor.codigo == "GAS-004"
    ts = fila.timestamp_utc
    ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
    assert ts == datetime(2026, 10, 7, 16, 25, 30, tzinfo=timezone.utc)


def test_cada_magnitud_es_un_registro_con_el_mismo_timestamp(db):
    resultado = enviar(
        db,
        payload(
            measurements={
                "co2": {"value": 410, "unit": "ppm"},
                "co": {"value": 2.5, "unit": "ppm"},
                "ch4": {"value": 120, "unit": "ppm"},
            }
        ),
    )
    assert resultado.almacenado
    filas = db.scalars(select(Medicion)).all()
    assert len(filas) == 3
    assert len({f.timestamp_utc for f in filas}) == 1
    assert {f.sensor_magnitud.magnitud for f in filas} == {"co2", "co", "ch4"}


def test_valores_en_los_limites_del_rango_son_validos(db):
    resultado = enviar(
        db,
        payload(measurements={"co2": {"value": 0, "unit": "ppm"}, "co": {"value": 1000, "unit": "ppm"}}),
    )
    assert resultado.almacenado


def test_acepta_bytes_como_los_entrega_paho(db):
    assert procesar_mensaje(db, TOPICO, json.dumps(payload()).encode("utf-8")).almacenado


# -- rechazos exigidos por la guía (pruebas 3 a 7) -----------------------------------------
def test_sensor_inexistente_se_rechaza(db):
    resultado = enviar(db, payload(sensor_id="NO-EXISTE-999"))
    assert not resultado.almacenado
    assert resultado.motivo is Motivo.SENSOR_INEXISTENTE
    assert total_mediciones(db) == 0


def test_unidad_incorrecta_se_rechaza(db):
    resultado = enviar(db, payload(measurements={"co2": {"value": 412.5, "unit": "ppb"}}))
    assert resultado.motivo is Motivo.UNIDAD_INCORRECTA
    assert total_mediciones(db) == 0


@pytest.mark.parametrize("valor", ["abc", "412.5", True, False, None, [412.5], {"v": 1}])
def test_tipo_de_dato_incorrecto_se_rechaza(db, valor):
    resultado = enviar(db, payload(measurements={"co2": {"value": valor, "unit": "ppm"}}))
    assert resultado.motivo is Motivo.TIPO_DATO_INVALIDO
    assert total_mediciones(db) == 0


def test_unidad_que_no_es_texto_se_rechaza(db):
    resultado = enviar(db, payload(measurements={"co2": {"value": 400, "unit": 5}}))
    assert resultado.motivo is Motivo.TIPO_DATO_INVALIDO


def test_sensor_id_que_no_es_texto_se_rechaza(db):
    resultado = enviar(db, payload(sensor_id=4))
    assert resultado.motivo is Motivo.TIPO_DATO_INVALIDO


def test_magnitud_incorrecta_se_rechaza(db):
    resultado = enviar(db, payload(measurements={"temperature": {"value": 20, "unit": "C"}}))
    assert resultado.motivo is Motivo.MAGNITUD_INVALIDA
    assert total_mediciones(db) == 0


@pytest.mark.parametrize(
    "timestamp",
    [
        "no-es-una-fecha",
        "",
        "2026-13-45T10:00:00Z",
        "2026-02-30T10:00:00Z",
        "2026-10-07T16:25:30",  # sin zona horaria
        "2026-10-07",
        "07/10/2026 16:25:30",
        1696696530,  # epoch numérico
        True,
        None,
        ["2026-10-07T16:25:30Z"],
    ],
)
def test_timestamp_invalido_se_rechaza(db, timestamp):
    resultado = enviar(db, payload(timestamp=timestamp))
    assert resultado.motivo is Motivo.TIMESTAMP_INVALIDO
    assert total_mediciones(db) == 0


def test_timestamp_en_el_futuro_se_rechaza(db):
    futuro = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resultado = enviar(db, payload(timestamp=futuro))
    assert resultado.motivo is Motivo.TIMESTAMP_INVALIDO
    assert total_mediciones(db) == 0


def test_timestamp_actual_se_acepta(db):
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert enviar(db, payload(timestamp=ahora)).almacenado


# -- otras validaciones ---------------------------------------------------------------------
@pytest.mark.parametrize("valor", [-0.1, 5000.01, 1e9, float("1e308")])
def test_valor_fuera_de_rango_se_rechaza(db, valor):
    resultado = enviar(db, payload(measurements={"co2": {"value": valor, "unit": "ppm"}}))
    assert resultado.motivo is Motivo.VALOR_FUERA_DE_RANGO
    assert total_mediciones(db) == 0


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_valores_no_finitos_se_rechazan(db, literal):
    crudo = (
        '{"sensor_id": "GAS-004", "timestamp": "2026-10-07T16:25:30Z", '
        '"measurements": {"co2": {"value": %s, "unit": "ppm"}}}' % literal
    )
    resultado = enviar(db, crudo)
    assert not resultado.almacenado
    assert total_mediciones(db) == 0


def test_si_una_magnitud_es_invalida_no_se_almacena_ninguna(db):
    resultado = enviar(
        db,
        payload(
            measurements={
                "co2": {"value": 410, "unit": "ppm"},  # válida
                "co": {"value": 2, "unit": "ppb"},  # unidad incorrecta
                "ch4": {"value": 99999, "unit": "ppm"},  # fuera de rango
            }
        ),
    )
    assert not resultado.almacenado
    assert resultado.motivo is Motivo.UNIDAD_INCORRECTA
    assert len(resultado.detalles) == 2  # se informan todos los problemas
    assert total_mediciones(db) == 0


@pytest.mark.parametrize(
    "mensaje",
    [
        {"timestamp": "2026-10-07T16:25:30Z", "measurements": {"co2": {"value": 1, "unit": "ppm"}}},
        {"sensor_id": "GAS-004", "measurements": {"co2": {"value": 1, "unit": "ppm"}}},
        {"sensor_id": "GAS-004", "timestamp": "2026-10-07T16:25:30Z"},
        {"sensor_id": "GAS-004", "timestamp": "2026-10-07T16:25:30Z", "measurements": {}},
        {"sensor_id": "GAS-004", "timestamp": "2026-10-07T16:25:30Z", "measurements": []},
        {"sensor_id": "GAS-004", "timestamp": "2026-10-07T16:25:30Z", "measurements": {"co2": 412}},
        {
            "sensor_id": "GAS-004",
            "timestamp": "2026-10-07T16:25:30Z",
            "measurements": {"co2": {"value": 1}},
        },
        {},
        [],
        "texto",
        42,
        None,
    ],
)
def test_estructura_invalida_se_rechaza(db, mensaje):
    resultado = enviar(db, json.dumps(mensaje))
    assert not resultado.almacenado
    assert resultado.motivo in {Motivo.ESTRUCTURA_INVALIDA, Motivo.TIPO_DATO_INVALIDO}
    assert total_mediciones(db) == 0


def test_campos_obligatorios_ausentes_son_estructura_invalida(db):
    resultado = enviar(db, {"measurements": {"co2": {"value": 1, "unit": "ppm"}}})
    assert resultado.motivo is Motivo.ESTRUCTURA_INVALIDA


def test_json_mal_formado_se_rechaza(db):
    resultado = enviar(db, '{"sensor_id": "GAS-004", ')
    assert resultado.motivo is Motivo.JSON_INVALIDO


def test_bytes_no_utf8_se_rechazan(db):
    assert procesar_mensaje(db, TOPICO, b"\xff\xfe\x00").motivo is Motivo.PAYLOAD_NO_DECODIFICABLE


def test_sensor_inactivo_se_rechaza(db):
    resultado = procesar_mensaje(
        db,
        "iot/sensors/AIRE-009/data",
        json.dumps(payload(sensor_id="AIRE-009", measurements={"pm25": {"value": 10, "unit": "ug/m3"}})),
    )
    assert resultado.motivo is Motivo.SENSOR_INACTIVO
    assert total_mediciones(db) == 0


def test_payload_de_otro_sensor_en_el_topico_asignado_se_rechaza(db):
    """El sensor existe (otro grupo), pero NO es el asignado: no se debe tocar su histórico."""
    resultado = enviar(
        db,
        payload(sensor_id="TEST-001", measurements={"temperature": {"value": 20, "unit": "C"}}),
    )
    assert resultado.motivo is Motivo.SENSOR_NO_ASIGNADO
    assert total_mediciones(db) == 0


@pytest.mark.parametrize("topico", ["iot/sensors/+/data", "otro/topico", "iot/sensors/GAS-004"])
def test_topico_que_no_corresponde_se_rechaza(db, topico):
    resultado = procesar_mensaje(db, topico, json.dumps(payload()))
    assert resultado.motivo is Motivo.SENSOR_NO_ASIGNADO
    assert total_mediciones(db) == 0


def test_error_de_base_de_datos_no_deja_datos_a_medias(db, monkeypatch):
    def falla(*args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("conexión perdida"))

    monkeypatch.setattr(ingesta.crud_medicion, "crear_varias", falla)
    resultado = enviar(db, payload())
    assert resultado.motivo is Motivo.ERROR_BASE_DE_DATOS
    assert total_mediciones(db) == 0


def test_simulacion_valida_sin_escribir_en_la_base(db):
    resultado = procesar_mensaje(db, TOPICO, json.dumps(payload()), guardar=False)
    assert resultado.valido and not resultado.almacenado
    assert resultado.mediciones[0].id is None
    assert resultado.resumen().startswith("VALIDO (simulacion")
    assert total_mediciones(db) == 0

    rechazado = procesar_mensaje(db, TOPICO, json.dumps(payload(sensor_id="X-1")), guardar=False)
    assert not rechazado.valido and rechazado.motivo is Motivo.SENSOR_INEXISTENTE


def test_resumen_para_el_log(db):
    assert enviar(db, payload()).resumen().startswith("ALMACENADO | sensor=GAS-004")
    assert "motivo=SENSOR_INEXISTENTE" in enviar(db, payload(sensor_id="X-1")).resumen()


def test_codigo_desde_topico():
    assert codigo_desde_topico("iot/sensors/GAS-004/data") == "GAS-004"
    assert codigo_desde_topico("iot/sensors/+/data") is None
    assert codigo_desde_topico("iot/sensors/GAS-004/data/extra") is None
    assert codigo_desde_topico("") is None
