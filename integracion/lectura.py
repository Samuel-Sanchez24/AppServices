"""Lectura de los datasets de origen.

Responsabilidad única: entregar los registros crudos de cada proveedor sin
interpretarlos. Los archivos de `datos/` se abren siempre en modo lectura y
nunca se modifican.
"""

import csv
import json
import os

from .errores import ErrorLectura

DELIMITADOR_B = ";"
COLUMNAS_B = (
    "record_code",
    "municipality",
    "country",
    "latitude_deg",
    "longitude_deg",
    "temp_celsius",
    "humidity_pct",
    "wind_kmh",
    "measurement_time",
    "origin_code",
)


def leer_proveedor_a(ruta):
    """Devuelve la lista de registros crudos del proveedor A (JSON).

    Lanza ErrorLectura si el archivo no existe o el JSON no es interpretable.
    """
    if not os.path.isfile(ruta):
        raise ErrorLectura("archivo inexistente: %s" % ruta)
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            contenido = json.load(archivo)
    except json.JSONDecodeError as exc:
        raise ErrorLectura("JSON no interpretable en %s: %s" % (ruta, exc)) from exc
    except OSError as exc:
        raise ErrorLectura("no se pudo leer %s: %s" % (ruta, exc)) from exc

    if isinstance(contenido, list):
        registros = contenido
    elif isinstance(contenido, dict):
        registros = contenido.get("records", [])
    else:
        raise ErrorLectura("estructura inesperada en %s" % ruta)

    if not isinstance(registros, list):
        raise ErrorLectura("'records' no es una lista en %s" % ruta)
    return registros


def leer_proveedor_b(ruta):
    """Devuelve la lista de filas crudas del proveedor B (CSV delimitado por ';').

    Cada elemento es un diccionario columna -> texto. Una fila defectuosa
    (número de columnas distinto al del encabezado) no interrumpe la lectura:
    se devuelve con la marca interna `_fila_defectuosa` para que la
    normalización la clasifique como error.
    """
    if not os.path.isfile(ruta):
        raise ErrorLectura("archivo inexistente: %s" % ruta)

    filas = []
    try:
        with open(ruta, "r", encoding="utf-8", newline="") as archivo:
            lector = csv.reader(archivo, delimiter=DELIMITADOR_B)
            try:
                encabezado = next(lector)
            except StopIteration:
                raise ErrorLectura("CSV vacío: %s" % ruta)
            encabezado = [c.strip().lstrip("﻿") for c in encabezado]
            for numero, campos in enumerate(lector, start=2):
                if not any(c.strip() for c in campos):
                    continue  # línea en blanco
                fila = dict(zip(encabezado, campos))
                fila["_linea"] = numero
                if len(campos) != len(encabezado):
                    fila["_fila_defectuosa"] = (
                        "la fila %d tiene %d columnas y el encabezado %d"
                        % (numero, len(campos), len(encabezado))
                    )
                filas.append(fila)
    except csv.Error as exc:
        raise ErrorLectura("CSV no interpretable en %s: %s" % (ruta, exc)) from exc
    except OSError as exc:
        raise ErrorLectura("no se pudo leer %s: %s" % (ruta, exc)) from exc
    return filas
