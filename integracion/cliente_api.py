"""Cliente HTTP de la API institucional.

Implementa las dos operaciones de `CONTRATO_API.md` (POST de registro y GET de
consulta), la interpretación de los códigos de respuesta y la política de
reintentos: 1 intento inicial + hasta 2 reintentos, máximo 3 intentos por
registro, y únicamente ante errores transitorios (5xx, timeout, pérdida de
conexión). Las respuestas 4xx nunca se reintentan.
"""

import time

import requests

from .contrato import HTTP_ACEPTADO, RUTA_MEDICIONES

# Estados posibles del envío de un registro.
ACEPTADO = "aceptado"
RECHAZADO_API = "rechazado_api"
ERROR_COMUNICACION = "error_comunicacion"

MAX_INTENTOS = 3
ESPERA_BASE_SEG = 1.0
TIMEOUT_SEG = 10.0
MAX_TEXTO_RESPUESTA = 300


class ClienteMediciones:
    """Cliente del contrato institucional.

    `sesion` se puede inyectar (por ejemplo un doble de prueba) para ejecutar
    las pruebas automatizadas sin tocar la API real.
    """

    def __init__(
        self,
        url_base,
        equipo,
        sesion=None,
        timeout=TIMEOUT_SEG,
        max_intentos=MAX_INTENTOS,
        espera_base=ESPERA_BASE_SEG,
        dormir=time.sleep,
    ):
        self.url_base = url_base.rstrip("/")
        self.equipo = equipo
        self.sesion = sesion if sesion is not None else requests.Session()
        self.timeout = timeout
        self.max_intentos = max(1, int(max_intentos))
        self.espera_base = espera_base
        self._dormir = dormir

    # ------------------------------------------------------------------ #
    # Utilidades internas
    # ------------------------------------------------------------------ #
    @property
    def url_mediciones(self):
        return self.url_base + RUTA_MEDICIONES

    def _headers(self):
        return {"Content-Type": "application/json", "X-Equipo": self.equipo}

    @staticmethod
    def _cuerpo(respuesta):
        """Devuelve el cuerpo interpretado; si no es JSON, un recorte del texto."""
        try:
            return respuesta.json()
        except ValueError:
            texto = (getattr(respuesta, "text", "") or "")[:MAX_TEXTO_RESPUESTA]
            return {"_respuesta_no_json": texto}

    # ------------------------------------------------------------------ #
    # Operaciones del contrato
    # ------------------------------------------------------------------ #
    def registrar(self, cuerpo):
        """POST /api/v1/mediciones con reintentos controlados.

        Devuelve un diccionario con: estado, codigo_http, intentos, respuesta y
        detalle. Nunca propaga excepciones de red.
        """
        ultimo = None
        for intento in range(1, self.max_intentos + 1):
            try:
                respuesta = self.sesion.post(
                    self.url_mediciones,
                    json=cuerpo,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.Timeout as exc:
                ultimo = self._transitorio(intento, "timeout: %s" % exc)
            except requests.ConnectionError as exc:
                ultimo = self._transitorio(intento, "pérdida de conexión: %s" % exc)
            except requests.RequestException as exc:
                ultimo = self._transitorio(intento, "error de red: %s" % exc)
            else:
                codigo = respuesta.status_code
                cuerpo_resp = self._cuerpo(respuesta)

                if codigo == HTTP_ACEPTADO:
                    return self._resultado(ACEPTADO, codigo, intento, cuerpo_resp,
                                           "registro aceptado por la API")
                if 400 <= codigo < 500:
                    # 400, 409, 422 y cualquier otro 4xx: no se reintenta.
                    return self._resultado(RECHAZADO_API, codigo, intento, cuerpo_resp,
                                           "la API rechazó el registro (HTTP %d)" % codigo)
                if codigo >= 500:
                    ultimo = self._resultado(
                        ERROR_COMUNICACION, codigo, intento, cuerpo_resp,
                        "error transitorio del servidor (HTTP %d)" % codigo,
                    )
                else:
                    # 2xx distinto de 201, 3xx: respuesta inesperada, sin reintento.
                    return self._resultado(
                        ERROR_COMUNICACION, codigo, intento, cuerpo_resp,
                        "respuesta HTTP inesperada (%d)" % codigo,
                    )

            if intento < self.max_intentos:
                self._dormir(self.espera_base * intento)

        ultimo["detalle"] = "agotados %d intentos: %s" % (self.max_intentos, ultimo["detalle"])
        return ultimo

    def consultar(self):
        """GET /api/v1/mediciones?equipo=<EQUIPO>. Devuelve estado y cuerpo."""
        try:
            respuesta = self.sesion.get(
                self.url_mediciones,
                params={"equipo": self.equipo},
                headers={"X-Equipo": self.equipo},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return {
                "estado": ERROR_COMUNICACION,
                "codigo_http": None,
                "respuesta": None,
                "detalle": "no fue posible consultar: %s" % exc,
            }

        cuerpo = self._cuerpo(respuesta)
        exito = respuesta.status_code == 200
        return {
            "estado": "ok" if exito else ERROR_COMUNICACION,
            "codigo_http": respuesta.status_code,
            "respuesta": cuerpo,
            "detalle": "consulta exitosa" if exito
            else "consulta no exitosa (HTTP %d)" % respuesta.status_code,
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def _resultado(estado, codigo, intentos, respuesta, detalle):
        return {
            "estado": estado,
            "codigo_http": codigo,
            "intentos": intentos,
            "respuesta": respuesta,
            "detalle": detalle,
        }

    def _transitorio(self, intento, detalle):
        return self._resultado(ERROR_COMUNICACION, None, intento, None, detalle)
