import time

import requests

from .contrato import HTTP_ACEPTADO, RUTA_MEDICIONES

ACEPTADO = "aceptado"
RECHAZADO_API = "rechazado_api"
ERROR_COMUNICACION = "error_comunicacion"

MAX_INTENTOS = 3
ESPERA_BASE_SEG = 1.0
TIMEOUT_SEG = 10.0
MAX_TEXTO_RESPUESTA = 300


class ClienteMediciones:

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

    @property
    def url_mediciones(self):
        return self.url_base + RUTA_MEDICIONES

    def _headers(self):
        return {"Content-Type": "application/json", "X-Equipo": self.equipo}

    @staticmethod
    def _cuerpo(respuesta):
        try:
            return respuesta.json()
        except ValueError:
            texto = (getattr(respuesta, "text", "") or "")[:MAX_TEXTO_RESPUESTA]
            return {"_respuesta_no_json": texto}

    def registrar(self, cuerpo):
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
                    return self._resultado(RECHAZADO_API, codigo, intento, cuerpo_resp,
                                           "la API rechazó el registro (HTTP %d)" % codigo)
                if codigo >= 500:
                    ultimo = self._resultado(
                        ERROR_COMUNICACION, codigo, intento, cuerpo_resp,
                        "error transitorio del servidor (HTTP %d)" % codigo,
                    )
                else:
                    return self._resultado(
                        ERROR_COMUNICACION, codigo, intento, cuerpo_resp,
                        "respuesta HTTP inesperada (%d)" % codigo,
                    )

            if intento < self.max_intentos:
                self._dormir(self.espera_base * intento)

        ultimo["detalle"] = "agotados %d intentos: %s" % (self.max_intentos, ultimo["detalle"])
        return ultimo

    def consultar(self):
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
