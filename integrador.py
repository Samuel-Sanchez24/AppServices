#!/usr/bin/env python3
"""Cliente integrador de mediciones meteorológicas — Taller 1.

Flujo: leer -> normalizar -> evidenciar -> validar -> enviar -> consultar -> reportar.

Uso:
    python integrador.py
"""

# --------------------------------------------------------------------------- #
# CONFIGURACIÓN (constantes configurables)
# --------------------------------------------------------------------------- #
URL_BASE = "https://appsweb.quantaiot.co"   # URL base de la API del docente
EQUIPO = "EQUIPO-06-APPSWEB"               # Identificador de equipo

RUTA_PROVEEDOR_A = "datos/proveedor_a.json"
RUTA_PROVEEDOR_B = "datos/proveedor_b.csv"
DIRECTORIO_SALIDA = "salida"
# --------------------------------------------------------------------------- #

import os
import sys

from integracion import lectura, normalizacion, reporte, validacion
from integracion.cliente_api import ACEPTADO, ERROR_COMUNICACION, ClienteMediciones
from integracion.contrato import ORIGEN_PROVEEDOR_A, ORIGEN_PROVEEDOR_B, cuerpo_api
from integracion.errores import ErrorLectura

RAIZ = os.path.dirname(os.path.abspath(__file__))


def _ruta(relativa):
    """Resuelve rutas respecto al directorio del proyecto, no al cwd."""
    return relativa if os.path.isabs(relativa) else os.path.join(RAIZ, relativa)


def log(mensaje):
    print(mensaje, flush=True)


# --------------------------------------------------------------------------- #
# Etapas
# --------------------------------------------------------------------------- #
def etapa_lectura():
    """Lee ambos datasets. Un dataset ilegible no detiene el proceso del otro."""
    crudos_a, crudos_b = [], []
    for ruta, lector, etiqueta, destino in (
        (RUTA_PROVEEDOR_A, lectura.leer_proveedor_a, "proveedor_a", "a"),
        (RUTA_PROVEEDOR_B, lectura.leer_proveedor_b, "proveedor_b", "b"),
    ):
        try:
            registros = lector(_ruta(ruta))
        except ErrorLectura as exc:
            log("  [!] %s: %s" % (etiqueta, exc))
            registros = []
        log("  %-12s %4d registros leídos" % (etiqueta, len(registros)))
        if destino == "a":
            crudos_a = registros
        else:
            crudos_b = registros
    return crudos_a, crudos_b


def etapa_normalizacion(crudos_a, crudos_b):
    norm_a, err_a = normalizacion.normalizar_lote(
        crudos_a, normalizacion.normalizar_a, ORIGEN_PROVEEDOR_A
    )
    norm_b, err_b = normalizacion.normalizar_lote(
        crudos_b, normalizacion.normalizar_b, ORIGEN_PROVEEDOR_B
    )
    normalizados = norm_a + norm_b
    errores = err_a + err_b
    log("  normalizados: %d   errores de normalización: %d" % (len(normalizados), len(errores)))
    for error in errores:
        log("    - %s  (%s: %s)" % (error["id_trazabilidad"], error["campo"], error["motivo"]))
    return normalizados, errores


def etapa_validacion(normalizados):
    validos, rechazados = validacion.clasificar(normalizados)
    log("  válidos localmente: %d   rechazados localmente: %d" % (len(validos), len(rechazados)))
    for registro in rechazados:
        log("    - %s  %s" % (registro["id_trazabilidad"], "; ".join(registro["errores_validacion"])))
    return validos, rechazados


def etapa_envio(cliente, validos):
    """Envía cada registro válido e interpreta la respuesta de la API."""
    envios = []
    for numero, registro in enumerate(validos, start=1):
        resultado = cliente.registrar(cuerpo_api(registro["medicion"]))
        resultado["id_trazabilidad"] = registro["id_trazabilidad"]
        resultado["origen"] = registro["origen"]
        envios.append(resultado)
        if resultado["estado"] != ACEPTADO:
            log("    [%s] %s -> %s (HTTP %s, intentos %s)" % (
                resultado["estado"], registro["id_trazabilidad"],
                resultado["detalle"], resultado["codigo_http"], resultado["intentos"]))
        if numero % 50 == 0:
            log("    ... %d/%d enviados" % (numero, len(validos)))
    return envios


def etapa_consulta(cliente):
    consulta = cliente.consultar()
    if consulta["estado"] == ERROR_COMUNICACION:
        log("  [!] %s" % consulta["detalle"])
    else:
        cuerpo = consulta["respuesta"]
        total = None
        if isinstance(cuerpo, dict):
            for clave in ("total", "registros", "cantidad", "count"):
                if isinstance(cuerpo.get(clave), int):
                    total = cuerpo[clave]
                    break
            if total is None and isinstance(cuerpo.get("mediciones"), list):
                total = len(cuerpo["mediciones"])
        log("  consulta GET equipo=%s -> HTTP %s, registros reportados: %s"
            % (cliente.equipo, consulta["codigo_http"], total if total is not None else "n/d"))
    return consulta


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #
def ejecutar():
    log("== 1. Lectura de datos ==")
    crudos_a, crudos_b = etapa_lectura()
    procesados_por_origen = {
        ORIGEN_PROVEEDOR_A: len(crudos_a),
        ORIGEN_PROVEEDOR_B: len(crudos_b),
    }

    log("== 2. Normalización ==")
    normalizados, errores_norm = etapa_normalizacion(crudos_a, crudos_b)

    log("== 3. Validación local ==")
    validos, rechazados = etapa_validacion(normalizados)

    salida = _ruta(DIRECTORIO_SALIDA)
    ruta_norm = reporte.guardar_normalizadas(salida, normalizados)
    log("  evidencia de normalización: %s (%d registros)" % (ruta_norm, len(normalizados)))

    log("== 4. Integración HTTP ==")
    log("  POST %s  (X-Equipo: %s)" % (URL_BASE.rstrip("/") + "/api/v1/mediciones", EQUIPO))
    cliente = ClienteMediciones(URL_BASE, EQUIPO)
    envios = etapa_envio(cliente, validos)

    log("== 5. Consulta de resultados ==")
    consulta = etapa_consulta(cliente)

    log("== 6. Reporte final ==")
    final = reporte.construir_reporte(
        procesados_por_origen, normalizados, errores_norm, validos, rechazados,
        envios, consulta, URL_BASE, EQUIPO,
    )
    ruta_reporte = reporte.guardar_reporte(salida, final)
    log("  reporte: %s" % ruta_reporte)
    for clave, valor in final["resumen"].items():
        log("    %-24s %s" % (clave, valor))
    return final


def main():
    try:
        ejecutar()
    except KeyboardInterrupt:
        log("\nEjecución interrumpida por el usuario.")
        return 130
    except Exception as exc:  # red de seguridad: nunca un traceback sin control
        log("Error no esperado durante la integración: %s: %s" % (type(exc).__name__, exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
