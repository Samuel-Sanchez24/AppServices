"""Pruebas de lectura: archivos inexistentes, JSON inválido y filas CSV defectuosas."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integracion import lectura
from integracion.errores import ErrorLectura

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _espera_error_lectura(funcion, ruta):
    try:
        funcion(ruta)
    except ErrorLectura:
        return True
    raise AssertionError("se esperaba ErrorLectura")


def test_archivo_inexistente_se_maneja_de_forma_controlada():
    assert _espera_error_lectura(lectura.leer_proveedor_a, "/no/existe/a.json")
    assert _espera_error_lectura(lectura.leer_proveedor_b, "/no/existe/b.csv")


def test_json_no_interpretable_se_maneja_de_forma_controlada():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write('{"records": [ {"a": 1},,, ]}')
        ruta = tmp.name
    try:
        assert _espera_error_lectura(lectura.leer_proveedor_a, ruta)
    finally:
        os.unlink(ruta)


def test_fila_csv_defectuosa_se_marca_y_no_detiene_la_lectura():
    contenido = (
        "record_code;municipality;country;latitude_deg;longitude_deg;"
        "temp_celsius;humidity_pct;wind_kmh;measurement_time;origin_code\n"
        "B-0001;Medellin;CO;6.26;-75.57;21.55;50.7;21.85;01/09/2026 06:00;PB\n"
        "B-0002;Medellin;CO;6.25\n"
        "B-0003;Cali;CO;3.45;-76.52;25.24;89.2;15.84;01/09/2026 07:30;PB\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as tmp:
        tmp.write(contenido)
        ruta = tmp.name
    try:
        filas = lectura.leer_proveedor_b(ruta)
        assert len(filas) == 3
        assert "_fila_defectuosa" in filas[1]
        assert "_fila_defectuosa" not in filas[0]
    finally:
        os.unlink(ruta)


def test_datasets_del_taller_se_leen_completos():
    registros = lectura.leer_proveedor_a(os.path.join(RAIZ, "datos", "proveedor_a.json"))
    filas = lectura.leer_proveedor_b(os.path.join(RAIZ, "datos", "proveedor_b.csv"))
    assert len(registros) == 200
    assert len(filas) == 200
