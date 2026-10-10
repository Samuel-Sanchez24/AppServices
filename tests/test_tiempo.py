"""Conversión UTC <-> hora de Colombia y validación de fechas."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.tiempo import (
    UTC,
    a_hora_colombia,
    a_utc,
    es_futuro,
    formatear_local,
    parsear_filtro_fecha,
    parsear_timestamp_mqtt,
)


def test_utc_se_muestra_en_hora_de_colombia():
    utc = datetime(2026, 10, 7, 16, 25, 30, tzinfo=UTC)
    assert formatear_local(utc) == "2026-10-07T11:25:30-05:00"
    assert a_hora_colombia(utc).utcoffset() == timedelta(hours=-5)


def test_cambio_de_dia_al_convertir():
    assert formatear_local(datetime(2026, 10, 8, 2, 0, 0, tzinfo=UTC)) == "2026-10-07T21:00:00-05:00"


def test_datetime_sin_zona_se_asume_utc():  # así los devuelve SQLite
    assert a_utc(datetime(2026, 10, 7, 16, 0, 0)).tzinfo == UTC


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("2026-10-07T16:25:30Z", datetime(2026, 10, 7, 16, 25, 30, tzinfo=UTC)),
        ("2026-10-07T11:25:30-05:00", datetime(2026, 10, 7, 16, 25, 30, tzinfo=UTC)),
        ("2026-10-07T16:25:30+00:00", datetime(2026, 10, 7, 16, 25, 30, tzinfo=UTC)),
        ("2026-10-07T16:25:30.5Z", datetime(2026, 10, 7, 16, 25, 30, 500000, tzinfo=UTC)),
        ("2026-10-07T16:25:30.123456789Z", datetime(2026, 10, 7, 16, 25, 30, 123456, tzinfo=UTC)),
        ("2026-10-07T16:25Z", datetime(2026, 10, 7, 16, 25, 0, tzinfo=UTC)),
    ],
)
def test_timestamp_mqtt_valido(texto, esperado):
    resultado = parsear_timestamp_mqtt(texto)
    assert resultado == esperado
    assert resultado.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "invalido",
        "2026-10-07",  # sin hora
        "2026-10-07T16:25:30",  # sin zona
        "2026-13-45T10:00:00Z",  # mes y día inexistentes
        "2026-02-30T10:00:00Z",  # 30 de febrero
        "2026-10-07T24:00:00Z",  # hora 24
        "2026-10-07T16:60:00Z",  # minuto 60
        "07/10/2026 16:25:30",
        "2026-10-07T16:25:30z",  # z minúscula
        "2026-10-07T16:25:30+25:00",  # desplazamiento imposible
        "1696696530",  # epoch como texto
    ],
)
def test_timestamp_mqtt_invalido(texto):
    with pytest.raises(ValueError):
        parsear_timestamp_mqtt(texto)


def test_filtro_con_zona_se_respeta():
    assert parsear_filtro_fecha("2026-10-07T16:00:00Z") == datetime(2026, 10, 7, 16, tzinfo=UTC)
    assert parsear_filtro_fecha("2026-10-07T11:00:00-05:00") == datetime(2026, 10, 7, 16, tzinfo=UTC)


def test_filtro_sin_zona_es_hora_de_colombia():
    assert parsear_filtro_fecha("2026-10-07T11:00:00") == datetime(2026, 10, 7, 16, tzinfo=UTC)


def test_filtro_solo_fecha_abarca_el_dia_completo():
    desde = parsear_filtro_fecha("2026-10-07")
    hasta = parsear_filtro_fecha("2026-10-07", fin_de_dia=True)
    assert desde == datetime(2026, 10, 7, 5, 0, tzinfo=UTC)  # 00:00 Colombia
    assert hasta == datetime(2026, 10, 8, 4, 59, 59, 999999, tzinfo=UTC)  # 23:59:59.999999 Colombia


def test_filtro_tolera_mas_sin_codificar():
    # '+' sin codificar llega a la API como espacio
    assert parsear_filtro_fecha("2026-10-07T11:00:00 05:00") == datetime(2026, 10, 7, 6, tzinfo=UTC)


@pytest.mark.parametrize("texto", ["", "ayer", "2026-13-01", "2026-10-07T25:00:00"])
def test_filtro_invalido(texto):
    with pytest.raises(ValueError):
        parsear_filtro_fecha(texto)


def test_es_futuro_respeta_la_tolerancia():
    ahora = datetime(2026, 10, 7, 16, 0, 0, tzinfo=timezone.utc)
    assert not es_futuro(ahora + timedelta(seconds=599), 600, ahora)
    assert es_futuro(ahora + timedelta(seconds=601), 600, ahora)
