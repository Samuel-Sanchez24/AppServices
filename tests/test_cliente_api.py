"""Pruebas del cliente HTTP con una sesión falsa: no se toca la API real."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dobles import RespuestaFalsa, SesionFalsa, medicion_valida, sin_conexion, timeout
from integracion.cliente_api import (
    ACEPTADO,
    ERROR_COMUNICACION,
    RECHAZADO_API,
    ClienteMediciones,
)
from integracion.contrato import cuerpo_api

URL = "http://api.ejemplo/"
EQUIPO = "equipo_prueba"


def _cliente(respuestas, respuesta_get=None):
    sesion = SesionFalsa(respuestas, respuesta_get)
    cliente = ClienteMediciones(URL, EQUIPO, sesion=sesion, dormir=lambda _s: None)
    return cliente, sesion


def test_201_es_aceptado_en_un_solo_intento():
    cliente, sesion = _cliente([RespuestaFalsa(201, {"id": 1})])
    resultado = cliente.registrar(medicion_valida())
    assert resultado["estado"] == ACEPTADO
    assert resultado["intentos"] == 1
    assert len(sesion.llamadas_post) == 1


def test_respuestas_4xx_no_se_reintentan():
    for codigo in (400, 409, 422, 404):
        cliente, sesion = _cliente([RespuestaFalsa(codigo, {"error": "x"})])
        resultado = cliente.registrar(medicion_valida())
        assert resultado["estado"] == RECHAZADO_API
        assert resultado["codigo_http"] == codigo
        assert len(sesion.llamadas_post) == 1, "4xx no debe reintentarse"


def test_5xx_reintenta_hasta_tres_intentos():
    cliente, sesion = _cliente([RespuestaFalsa(500, {"error": "interno"})] * 3)
    resultado = cliente.registrar(medicion_valida())
    assert resultado["estado"] == ERROR_COMUNICACION
    assert resultado["intentos"] == 3
    assert len(sesion.llamadas_post) == 3


def test_5xx_seguido_de_201_termina_aceptado():
    cliente, sesion = _cliente([RespuestaFalsa(503, {}), RespuestaFalsa(201, {"ok": True})])
    resultado = cliente.registrar(medicion_valida())
    assert resultado["estado"] == ACEPTADO
    assert resultado["intentos"] == 2
    assert len(sesion.llamadas_post) == 2


def test_timeout_y_perdida_de_conexion_agotan_los_intentos():
    for fabrica in (timeout, sin_conexion):
        cliente, sesion = _cliente([fabrica(), fabrica(), fabrica()])
        resultado = cliente.registrar(medicion_valida())
        assert resultado["estado"] == ERROR_COMUNICACION
        assert len(sesion.llamadas_post) == 3
        assert "agotados 3 intentos" in resultado["detalle"]


def test_respuesta_no_json_no_rompe_el_programa():
    cliente, _ = _cliente([RespuestaFalsa(201, cuerpo=None, texto="<html>creado</html>")])
    resultado = cliente.registrar(medicion_valida())
    assert resultado["estado"] == ACEPTADO
    assert "_respuesta_no_json" in resultado["respuesta"]


def test_respuesta_http_inesperada_no_rompe_el_programa():
    cliente, sesion = _cliente([RespuestaFalsa(204, {})])
    resultado = cliente.registrar(medicion_valida())
    assert resultado["estado"] == ERROR_COMUNICACION
    assert "inesperada" in resultado["detalle"]
    assert len(sesion.llamadas_post) == 1


def test_headers_ruta_y_body_conforme_al_contrato():
    cliente, sesion = _cliente([RespuestaFalsa(201, {})])
    registro = {"id_trazabilidad": "A-0001", "origen": "proveedor_a",
                "medicion": medicion_valida()}
    cliente.registrar(cuerpo_api(registro["medicion"]))
    llamada = sesion.llamadas_post[0]
    assert llamada["url"] == "http://api.ejemplo/api/v1/mediciones"
    assert llamada["headers"]["Content-Type"] == "application/json"
    assert llamada["headers"]["X-Equipo"] == EQUIPO
    # El identificador interno de trazabilidad no viaja en el body.
    assert "id_trazabilidad" not in llamada["json"]
    assert sorted(llamada["json"].keys()) == sorted(medicion_valida().keys())


def test_consulta_get_usa_query_param_equipo():
    respuesta = RespuestaFalsa(200, {"equipo": EQUIPO, "total": 2, "mediciones": [{}, {}]})
    cliente, sesion = _cliente([], respuesta_get=respuesta)
    consulta = cliente.consultar()
    assert consulta["estado"] == "ok"
    assert consulta["codigo_http"] == 200
    assert sesion.llamadas_get[0]["params"] == {"equipo": EQUIPO}


def test_consulta_con_fallo_de_red_no_lanza_excepcion():
    cliente, _ = _cliente([], respuesta_get=timeout())
    consulta = cliente.consultar()
    assert consulta["estado"] == ERROR_COMUNICACION
    assert consulta["respuesta"] is None
