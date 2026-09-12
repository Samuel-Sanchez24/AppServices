"""Pruebas de validación local: reglas del contrato y casos límite."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dobles import medicion_valida
from integracion import validacion


# 3. Registro válido ---------------------------------------------------------
def test_registro_valido_no_tiene_errores():
    assert validacion.validar(medicion_valida()) == []


# 4. Registro inválido -------------------------------------------------------
def test_registro_invalido_humedad_fuera_de_rango():
    errores = validacion.validar(medicion_valida(humedad=108.4))
    assert len(errores) == 1
    assert "humedad" in errores[0]


def test_registro_invalido_latitud_longitud_y_viento():
    assert validacion.validar(medicion_valida(latitud=95.245))
    assert validacion.validar(medicion_valida(longitud=-190.75))
    assert validacion.validar(medicion_valida(viento_kmh=-8.64))


def test_registro_invalido_texto_vacio_y_origen_no_permitido():
    assert "ciudad vacía" in validacion.validar(medicion_valida(ciudad=""))
    assert "pais vacío" in validacion.validar(medicion_valida(pais=""))
    assert validacion.validar(medicion_valida(origen="PB"))


# 5. Caso límite -------------------------------------------------------------
def test_caso_limite_valores_en_la_frontera_son_validos():
    """Los extremos documentados del contrato son inclusivos."""
    assert validacion.validar(medicion_valida(humedad=0.0)) == []
    assert validacion.validar(medicion_valida(humedad=100.0)) == []
    assert validacion.validar(medicion_valida(viento_kmh=0.0)) == []
    assert validacion.validar(medicion_valida(latitud=-90.0, longitud=-180.0)) == []
    assert validacion.validar(medicion_valida(latitud=90.0, longitud=180.0)) == []
    # Temperaturas negativas son numéricas y por tanto válidas.
    assert validacion.validar(medicion_valida(temperatura_c=-12.5)) == []
    # Un paso fuera de la frontera ya es rechazo.
    assert validacion.validar(medicion_valida(humedad=100.01))
    assert validacion.validar(medicion_valida(viento_kmh=-0.01))


def test_clasificar_conserva_ambos_grupos_y_marca_estado():
    registros = [
        {"id_trazabilidad": "A-0001", "origen": "proveedor_a", "medicion": medicion_valida()},
        {"id_trazabilidad": "A-0015", "origen": "proveedor_a",
         "medicion": medicion_valida(humedad=108.4)},
    ]
    validos, rechazados = validacion.clasificar(registros)
    assert [r["id_trazabilidad"] for r in validos] == ["A-0001"]
    assert [r["id_trazabilidad"] for r in rechazados] == ["A-0015"]
    assert registros[0]["estado_validacion"] == validacion.ESTADO_VALIDO
    assert registros[1]["estado_validacion"] == validacion.ESTADO_RECHAZADO
    # Ambos siguen en la lista original -> ambos van a normalizadas.json
    assert len(registros) == 2
