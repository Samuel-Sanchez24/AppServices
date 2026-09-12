"""Generación de evidencias: salida/normalizadas.json y salida/reporte.json."""

import json
import os
from datetime import datetime

from .cliente_api import ACEPTADO, ERROR_COMUNICACION, RECHAZADO_API
from .validacion import ESTADO_RECHAZADO, ESTADO_VALIDO

ARCHIVO_NORMALIZADAS = "normalizadas.json"
ARCHIVO_REPORTE = "reporte.json"


def _escribir_json(ruta, contenido):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_normalizadas(directorio, normalizados):
    """Escribe todos los registros que sí pudieron llevarse al contrato.

    Incluye los rechazados por la validación local, tal como exige el taller.
    Los campos `id_trazabilidad`, `estado_validacion` y `errores_validacion` son
    internos (evidencia) y no forman parte del body enviado a la API.
    """
    ruta = os.path.join(directorio, ARCHIVO_NORMALIZADAS)
    contenido = [
        {
            "id_trazabilidad": r["id_trazabilidad"],
            "origen": r["origen"],
            "estado_validacion": r.get("estado_validacion", ESTADO_VALIDO),
            "errores_validacion": r.get("errores_validacion", []),
            "medicion": r["medicion"],
        }
        for r in normalizados
    ]
    _escribir_json(ruta, contenido)
    return ruta


def construir_reporte(
    procesados_por_origen,
    normalizados,
    errores_normalizacion,
    validos,
    rechazados_local,
    envios,
    consulta,
    url_base,
    equipo,
):
    """Arma la estructura del reporte final con conteos y trazabilidad."""
    aceptados = [e for e in envios if e["estado"] == ACEPTADO]
    rechazados_api = [e for e in envios if e["estado"] == RECHAZADO_API]
    errores_com = [e for e in envios if e["estado"] == ERROR_COMUNICACION]

    procesados = sum(procesados_por_origen.values())

    return {
        "ejecucion": {
            "fecha_hora": datetime.now().astimezone().isoformat(),
            "url_base": url_base,
            "equipo": equipo,
        },
        "resumen": {
            "procesados": procesados,
            "procesados_por_origen": procesados_por_origen,
            "normalizados": len(normalizados),
            "errores_normalizacion": len(errores_normalizacion),
            "validos_localmente": len(validos),
            "rechazados_localmente": len(rechazados_local),
            "enviados": len(envios),
            "aceptados_api": len(aceptados),
            "rechazados_api": len(rechazados_api),
            "errores_comunicacion": len(errores_com),
        },
        "consulta_final": consulta,
        "detalle": {
            "errores_normalizacion": errores_normalizacion,
            "rechazados_localmente": [
                {
                    "id_trazabilidad": r["id_trazabilidad"],
                    "origen": r["origen"],
                    "errores": r["errores_validacion"],
                }
                for r in rechazados_local
            ],
            "rechazados_api": [_resumen_envio(e) for e in rechazados_api],
            "errores_comunicacion": [_resumen_envio(e) for e in errores_com],
            "aceptados_api": [
                {
                    "id_trazabilidad": e["id_trazabilidad"],
                    "origen": e["origen"],
                    "codigo_http": e["codigo_http"],
                    "intentos": e["intentos"],
                }
                for e in aceptados
            ],
        },
        "trazabilidad": _trazabilidad(normalizados, errores_normalizacion, envios),
    }


def _resumen_envio(envio):
    return {
        "id_trazabilidad": envio["id_trazabilidad"],
        "origen": envio["origen"],
        "codigo_http": envio["codigo_http"],
        "intentos": envio["intentos"],
        "detalle": envio["detalle"],
        "respuesta": envio["respuesta"],
    }


def _trazabilidad(normalizados, errores_normalizacion, envios):
    """Una línea por registro identificado, con su resultado final."""
    por_id = {e["id_trazabilidad"]: e for e in envios}
    filas = []

    for error in errores_normalizacion:
        filas.append(
            {
                "id_trazabilidad": error["id_trazabilidad"],
                "origen": error["origen"],
                "resultado": "error_normalizacion",
                "detalle": "%s: %s" % (error["campo"], error["motivo"]),
            }
        )

    for registro in normalizados:
        id_traza = registro["id_trazabilidad"]
        if registro.get("estado_validacion") == ESTADO_RECHAZADO:
            filas.append(
                {
                    "id_trazabilidad": id_traza,
                    "origen": registro["origen"],
                    "resultado": ESTADO_RECHAZADO,
                    "detalle": "; ".join(registro["errores_validacion"]),
                }
            )
            continue
        envio = por_id.get(id_traza)
        if envio is None:
            filas.append(
                {
                    "id_trazabilidad": id_traza,
                    "origen": registro["origen"],
                    "resultado": "no_enviado",
                    "detalle": "válido localmente pero sin envío registrado",
                }
            )
            continue
        filas.append(
            {
                "id_trazabilidad": id_traza,
                "origen": registro["origen"],
                "resultado": envio["estado"],
                "codigo_http": envio["codigo_http"],
                "intentos": envio["intentos"],
                "detalle": envio["detalle"],
            }
        )
    return filas


def guardar_reporte(directorio, reporte):
    ruta = os.path.join(directorio, ARCHIVO_REPORTE)
    _escribir_json(ruta, reporte)
    return ruta
