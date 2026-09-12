"""Normalización: de la representación de cada proveedor al contrato institucional.

Criterio usado en todo el módulo (documentado en ANALISIS.md):

* Campos numéricos y de fecha: sólo se normalizan si el valor presente admite
  conversión. Un nulo, una cadena vacía, un texto no numérico o una fecha no
  interpretable son **errores de normalización**.
* Campos de texto (`ciudad`, `pais`): siempre admiten representación. Si están
  ausentes, nulos o vacíos se normalizan como cadena vacía y es la validación
  local la que los rechaza por la regla "no vacío" del contrato.
"""

from datetime import datetime, timedelta, timezone

from .contrato import ORIGEN_PROVEEDOR_A, ORIGEN_PROVEEDOR_B
from .errores import ErrorNormalizacion

# Los datasets reportan hora local de Colombia (UTC-05:00).
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

# Formatos de fecha aceptados por proveedor.
FORMATOS_FECHA_B = ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S")

DECIMALES = 2


# --------------------------------------------------------------------------- #
# Conversores elementales
# --------------------------------------------------------------------------- #
def a_numero(valor, campo):
    """Convierte `valor` a float o lanza ErrorNormalizacion."""
    if valor is None:
        raise ErrorNormalizacion(campo, valor, "valor nulo o ausente")
    if isinstance(valor, bool):
        raise ErrorNormalizacion(campo, valor, "booleano no es numérico")
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        texto = valor.strip().replace(",", ".")
        if not texto:
            raise ErrorNormalizacion(campo, valor, "valor vacío")
        try:
            return float(texto)
        except ValueError:
            raise ErrorNormalizacion(campo, valor, "texto no convertible a número")
    raise ErrorNormalizacion(campo, valor, "tipo no convertible a número")


def a_texto(valor):
    """Normaliza un campo de texto. Nunca falla: ausente o nulo -> cadena vacía."""
    if valor is None:
        return ""
    return str(valor).strip()


def a_iso8601(valor, campo, formatos=()):
    """Convierte una fecha/hora a ISO 8601 con zona horaria explícita."""
    if valor is None:
        raise ErrorNormalizacion(campo, valor, "fecha ausente")
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise ErrorNormalizacion(campo, valor, "fecha vacía")
        momento = None
        try:
            momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            for formato in formatos:
                try:
                    momento = datetime.strptime(texto, formato)
                    break
                except ValueError:
                    continue
        if momento is None:
            raise ErrorNormalizacion(campo, valor, "fecha no interpretable")
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=ZONA_COLOMBIA)
        return momento.isoformat()
    raise ErrorNormalizacion(campo, valor, "tipo no admitido para fecha")


def fahrenheit_a_celsius(grados_f):
    """°F -> °C, redondeado a 2 decimales."""
    return round((grados_f - 32.0) * 5.0 / 9.0, DECIMALES)


def ms_a_kmh(metros_por_segundo):
    """m/s -> km/h, redondeado a 2 decimales."""
    return round(metros_por_segundo * 3.6, DECIMALES)


# --------------------------------------------------------------------------- #
# Normalizadores por proveedor
# --------------------------------------------------------------------------- #
def _bloque(registro, clave):
    valor = registro.get(clave) if isinstance(registro, dict) else None
    return valor if isinstance(valor, dict) else {}


def normalizar_a(registro, indice):
    """Normaliza un registro del proveedor A. Devuelve (id_trazabilidad, medicion)."""
    if not isinstance(registro, dict):
        raise ErrorNormalizacion("registro", registro, "el registro no es un objeto")

    id_traza = a_texto(registro.get("provider_record_id")) or "proveedor_a#%d" % indice
    estacion = _bloque(registro, "station")
    ubicacion = _bloque(registro, "location")
    medidas = _bloque(registro, "measurements")

    medicion = {
        "ciudad": a_texto(estacion.get("city_name")),
        "pais": a_texto(estacion.get("country_code")),
        "latitud": round(a_numero(ubicacion.get("lat"), "lat"), 6),
        "longitud": round(a_numero(ubicacion.get("lon"), "lon"), 6),
        "temperatura_c": fahrenheit_a_celsius(
            a_numero(medidas.get("temperature_f"), "temperature_f")
        ),
        "humedad": round(a_numero(medidas.get("relative_humidity"), "relative_humidity"), DECIMALES),
        "viento_kmh": ms_a_kmh(a_numero(medidas.get("wind_speed_ms"), "wind_speed_ms")),
        "fecha_hora": a_iso8601(registro.get("observed_at"), "observed_at"),
        "origen": ORIGEN_PROVEEDOR_A,
    }
    return id_traza, medicion


def normalizar_b(fila, indice):
    """Normaliza una fila del proveedor B. Devuelve (id_trazabilidad, medicion)."""
    if not isinstance(fila, dict):
        raise ErrorNormalizacion("fila", fila, "la fila no es un registro")

    id_traza = a_texto(fila.get("record_code")) or "proveedor_b#%d" % indice
    if fila.get("_fila_defectuosa"):
        raise ErrorNormalizacion("fila", None, fila["_fila_defectuosa"])

    medicion = {
        "ciudad": a_texto(fila.get("municipality")),
        "pais": a_texto(fila.get("country")),
        "latitud": round(a_numero(fila.get("latitude_deg"), "latitude_deg"), 6),
        "longitud": round(a_numero(fila.get("longitude_deg"), "longitude_deg"), 6),
        "temperatura_c": round(a_numero(fila.get("temp_celsius"), "temp_celsius"), DECIMALES),
        "humedad": round(a_numero(fila.get("humidity_pct"), "humidity_pct"), DECIMALES),
        "viento_kmh": round(a_numero(fila.get("wind_kmh"), "wind_kmh"), DECIMALES),
        "fecha_hora": a_iso8601(
            fila.get("measurement_time"), "measurement_time", FORMATOS_FECHA_B
        ),
        "origen": ORIGEN_PROVEEDOR_B,
    }
    return id_traza, medicion


def normalizar_lote(registros, normalizador, origen):
    """Normaliza una colección completa.

    Devuelve (normalizados, errores) donde `normalizados` es una lista de
    diccionarios {id_trazabilidad, origen, medicion} y `errores` una lista de
    diccionarios {id_trazabilidad, origen, campo, valor, motivo}.
    """
    normalizados, errores = [], []
    for indice, crudo in enumerate(registros, start=1):
        try:
            id_traza, medicion = normalizador(crudo, indice)
        except ErrorNormalizacion as exc:
            errores.append(
                {
                    "id_trazabilidad": _id_de_respaldo(crudo, origen, indice),
                    "origen": origen,
                    "campo": exc.campo,
                    "valor": repr(exc.valor),
                    "motivo": exc.motivo,
                }
            )
            continue
        normalizados.append(
            {"id_trazabilidad": id_traza, "origen": origen, "medicion": medicion}
        )
    return normalizados, errores


def _id_de_respaldo(crudo, origen, indice):
    """Identificador de trazabilidad aun cuando el registro falló al normalizar."""
    if isinstance(crudo, dict):
        for clave in ("provider_record_id", "record_code"):
            valor = a_texto(crudo.get(clave))
            if valor:
                return valor
    return "%s#%d" % (origen, indice)
