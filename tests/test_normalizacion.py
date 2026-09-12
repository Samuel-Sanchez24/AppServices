"""Pruebas de normalización: transformaciones, unidades y errores de conversión."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integracion import normalizacion
from integracion.contrato import CAMPOS_CONTRATO
from integracion.errores import ErrorNormalizacion

REGISTRO_A = {
    "provider_record_id": "A-0001",
    "station": {"code": "STA-02", "city_name": "Medellin", "country_code": "CO"},
    "location": {"lat": 6.242282, "lon": -75.595933},
    "measurements": {
        "temperature_f": 66.1,
        "relative_humidity": 81.3,
        "wind_speed_ms": 8.47,
    },
    "observed_at": "2026-09-01T00:00:00-05:00",
    "source": "weather_provider_a",
}

FILA_B = {
    "record_code": "B-0001",
    "municipality": "Medellin",
    "country": "CO",
    "latitude_deg": "6.261520",
    "longitude_deg": "-75.575842",
    "temp_celsius": "21.55",
    "humidity_pct": "50.7",
    "wind_kmh": "21.85",
    "measurement_time": "01/09/2026 06:00",
    "origin_code": "PB",
}


# 1. Transformación correcta -------------------------------------------------
def test_transformacion_correcta_proveedor_a():
    id_traza, medicion = normalizacion.normalizar_a(REGISTRO_A, 1)
    assert id_traza == "A-0001"
    assert sorted(medicion.keys()) == sorted(CAMPOS_CONTRATO)
    assert medicion["ciudad"] == "Medellin"
    assert medicion["pais"] == "CO"
    assert medicion["latitud"] == 6.242282
    assert medicion["longitud"] == -75.595933
    assert medicion["humedad"] == 81.3
    assert medicion["fecha_hora"] == "2026-09-01T00:00:00-05:00"
    assert medicion["origen"] == "proveedor_a"


def test_transformacion_correcta_proveedor_b():
    id_traza, medicion = normalizacion.normalizar_b(FILA_B, 1)
    assert id_traza == "B-0001"
    assert sorted(medicion.keys()) == sorted(CAMPOS_CONTRATO)
    assert medicion["origen"] == "proveedor_b"
    # El CSV entrega texto; el contrato exige números.
    assert isinstance(medicion["latitud"], float)
    assert isinstance(medicion["temperatura_c"], float)
    assert medicion["fecha_hora"] == "2026-09-01T06:00:00-05:00"


# 2. Conversión de unidades --------------------------------------------------
def test_conversion_de_unidades_fahrenheit_y_ms():
    assert normalizacion.fahrenheit_a_celsius(66.1) == 18.94
    assert normalizacion.fahrenheit_a_celsius(32.0) == 0.0
    assert normalizacion.fahrenheit_a_celsius(212.0) == 100.0
    assert normalizacion.ms_a_kmh(8.47) == 30.49
    assert normalizacion.ms_a_kmh(0.0) == 0.0

    _, medicion = normalizacion.normalizar_a(REGISTRO_A, 1)
    assert medicion["temperatura_c"] == 18.94     # 66.1 °F
    assert medicion["viento_kmh"] == 30.49        # 8.47 m/s


def test_proveedor_b_no_requiere_conversion_de_unidades():
    _, medicion = normalizacion.normalizar_b(FILA_B, 1)
    assert medicion["temperatura_c"] == 21.55     # ya venía en °C
    assert medicion["viento_kmh"] == 21.85        # ya venía en km/h


# 3. Errores de normalización ------------------------------------------------
def _espera_error(funcion, *args):
    try:
        funcion(*args)
    except ErrorNormalizacion as exc:
        return exc
    raise AssertionError("se esperaba ErrorNormalizacion y no se lanzó")


def test_error_normalizacion_temperatura_no_numerica():
    registro = dict(REGISTRO_A, measurements=dict(REGISTRO_A["measurements"], temperature_f="N/A"))
    exc = _espera_error(normalizacion.normalizar_a, registro, 82)
    assert exc.campo == "temperature_f"


def test_error_normalizacion_temperatura_nula():
    registro = dict(REGISTRO_A, measurements=dict(REGISTRO_A["measurements"], temperature_f=None))
    _espera_error(normalizacion.normalizar_a, registro, 173)


def test_error_normalizacion_fecha_invalida_o_ausente():
    registro = dict(REGISTRO_A, observed_at="09-XX-2026 25:61")
    _espera_error(normalizacion.normalizar_a, registro, 174)

    sin_fecha = {k: v for k, v in REGISTRO_A.items() if k != "observed_at"}
    _espera_error(normalizacion.normalizar_a, sin_fecha, 40)

    fila = dict(FILA_B, measurement_time="")
    _espera_error(normalizacion.normalizar_b, fila, 76)

    fila = dict(FILA_B, measurement_time="31/13/2026 28:75")
    _espera_error(normalizacion.normalizar_b, fila, 171)


def test_texto_ausente_se_normaliza_vacio_no_es_error():
    """País ausente no impide la representación: se resuelve en validación local."""
    registro = dict(REGISTRO_A, station={"code": "STA-08", "city_name": "Cali"})
    _, medicion = normalizacion.normalizar_a(registro, 150)
    assert medicion["pais"] == ""


def test_identificador_de_trazabilidad_cuando_falta_el_del_proveedor():
    registro = {k: v for k, v in REGISTRO_A.items() if k != "provider_record_id"}
    id_traza, _ = normalizacion.normalizar_a(registro, 7)
    assert id_traza == "proveedor_a#7"


def test_normalizar_lote_separa_validos_y_errores():
    malo = dict(REGISTRO_A, provider_record_id="A-9999",
                measurements=dict(REGISTRO_A["measurements"], temperature_f="error"))
    normalizados, errores = normalizacion.normalizar_lote(
        [REGISTRO_A, malo], normalizacion.normalizar_a, "proveedor_a"
    )
    assert len(normalizados) == 1 and len(errores) == 1
    assert errores[0]["id_trazabilidad"] == "A-9999"
