"""Validación local contra las reglas del contrato institucional.

La validación local no reemplaza la del servidor: sólo evita enviar registros
que ya sabemos que incumplen el contrato.
"""

from .contrato import (
    CAMPOS_CONTRATO,
    ORIGENES_PERMITIDOS,
    RANGO_HUMEDAD,
    RANGO_LATITUD,
    RANGO_LONGITUD,
    VIENTO_MINIMO,
)

ESTADO_VALIDO = "valido"
ESTADO_RECHAZADO = "rechazado_localmente"


def validar(medicion):
    """Devuelve la lista de reglas incumplidas. Lista vacía => registro válido."""
    errores = []

    for campo in CAMPOS_CONTRATO:
        if campo not in medicion:
            errores.append("campo obligatorio ausente: %s" % campo)

    if not str(medicion.get("ciudad", "")).strip():
        errores.append("ciudad vacía")
    if not str(medicion.get("pais", "")).strip():
        errores.append("pais vacío")

    _rango(errores, medicion, "latitud", RANGO_LATITUD)
    _rango(errores, medicion, "longitud", RANGO_LONGITUD)
    _rango(errores, medicion, "humedad", RANGO_HUMEDAD)

    temperatura = medicion.get("temperatura_c")
    if not isinstance(temperatura, (int, float)) or isinstance(temperatura, bool):
        errores.append("temperatura_c no es numérica")

    viento = medicion.get("viento_kmh")
    if not isinstance(viento, (int, float)) or isinstance(viento, bool):
        errores.append("viento_kmh no es numérico")
    elif viento < VIENTO_MINIMO:
        errores.append("viento_kmh negativo (%s)" % viento)

    if not str(medicion.get("fecha_hora", "")).strip():
        errores.append("fecha_hora vacía")

    if medicion.get("origen") not in ORIGENES_PERMITIDOS:
        errores.append("origen no permitido: %r" % medicion.get("origen"))

    return errores


def _rango(errores, medicion, campo, limites):
    valor = medicion.get(campo)
    minimo, maximo = limites
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        errores.append("%s no es numérico" % campo)
        return
    if not minimo <= valor <= maximo:
        errores.append("%s fuera de rango [%s, %s]: %s" % (campo, minimo, maximo, valor))


def clasificar(normalizados):
    """Separa los registros normalizados en válidos y rechazados localmente.

    Añade a cada registro las claves `estado_validacion` y `errores_validacion`,
    de modo que `salida/normalizadas.json` conserve ambos grupos.
    """
    validos, rechazados = [], []
    for registro in normalizados:
        errores = validar(registro["medicion"])
        registro["errores_validacion"] = errores
        registro["estado_validacion"] = ESTADO_VALIDO if not errores else ESTADO_RECHAZADO
        (validos if not errores else rechazados).append(registro)
    return validos, rechazados
