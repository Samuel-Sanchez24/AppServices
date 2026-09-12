"""Dobles de prueba: aíslan las pruebas de la API real (no hay red en los tests)."""

import requests


class RespuestaFalsa:
    def __init__(self, status_code, cuerpo=None, texto=None):
        self.status_code = status_code
        self._cuerpo = cuerpo
        self.text = texto if texto is not None else ""

    def json(self):
        if self._cuerpo is None:
            raise ValueError("cuerpo no es JSON")
        return self._cuerpo


class SesionFalsa:
    """Devuelve, en orden, las respuestas o excepciones programadas."""

    def __init__(self, respuestas, respuesta_get=None):
        self.respuestas = list(respuestas)
        self.respuesta_get = respuesta_get or RespuestaFalsa(
            200, {"equipo": "equipo_prueba", "total": 0, "mediciones": []}
        )
        self.llamadas_post = []
        self.llamadas_get = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.llamadas_post.append(
            {"url": url, "json": json, "headers": headers, "timeout": timeout}
        )
        siguiente = self.respuestas.pop(0) if self.respuestas else RespuestaFalsa(201, {"ok": True})
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    def get(self, url, params=None, headers=None, timeout=None):
        self.llamadas_get.append({"url": url, "params": params, "headers": headers})
        if isinstance(self.respuesta_get, Exception):
            raise self.respuesta_get
        return self.respuesta_get


def timeout():
    return requests.Timeout("tiempo de espera agotado")


def sin_conexion():
    return requests.ConnectionError("conexión perdida")


def medicion_valida(**cambios):
    base = {
        "ciudad": "Medellin",
        "pais": "CO",
        "latitud": 6.242282,
        "longitud": -75.595933,
        "temperatura_c": 18.94,
        "humedad": 81.3,
        "viento_kmh": 30.49,
        "fecha_hora": "2026-09-01T00:00:00-05:00",
        "origen": "proveedor_a",
    }
    base.update(cambios)
    return base
