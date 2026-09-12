"""Pruebas del reporte final: los conteos deben cuadrar y conservar trazabilidad."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dobles import medicion_valida
from integracion import reporte, validacion


def _escenario():
    normalizados = [
        {"id_trazabilidad": "A-0001", "origen": "proveedor_a", "medicion": medicion_valida()},
        {"id_trazabilidad": "A-0015", "origen": "proveedor_a",
         "medicion": medicion_valida(humedad=108.4)},
    ]
    validos, rechazados = validacion.clasificar(normalizados)
    errores_norm = [{"id_trazabilidad": "A-0082", "origen": "proveedor_a",
                     "campo": "temperature_f", "valor": "'N/A'",
                     "motivo": "texto no convertible a número"}]
    envios = [{"id_trazabilidad": "A-0001", "origen": "proveedor_a", "estado": "aceptado",
               "codigo_http": 201, "intentos": 1, "respuesta": {"ok": True},
               "detalle": "registro aceptado por la API"}]
    consulta = {"estado": "ok", "codigo_http": 200,
                "respuesta": {"equipo": "equipo_prueba", "total": 1}, "detalle": "consulta exitosa"}
    return normalizados, errores_norm, validos, rechazados, envios, consulta


def test_conteos_del_reporte_cuadran():
    normalizados, errores_norm, validos, rechazados, envios, consulta = _escenario()
    final = reporte.construir_reporte(
        {"proveedor_a": 3, "proveedor_b": 0}, normalizados, errores_norm,
        validos, rechazados, envios, consulta, "http://api", "equipo_prueba",
    )
    resumen = final["resumen"]
    assert resumen["procesados"] == 3
    assert resumen["normalizados"] + resumen["errores_normalizacion"] == resumen["procesados"]
    assert resumen["validos_localmente"] + resumen["rechazados_localmente"] == resumen["normalizados"]
    assert resumen["enviados"] == resumen["validos_localmente"]
    assert resumen["aceptados_api"] == 1
    assert resumen["rechazados_api"] == 0
    assert resumen["errores_comunicacion"] == 0
    # Trazabilidad: una línea por registro identificado.
    assert len(final["trazabilidad"]) == 3
    resultados = {f["id_trazabilidad"]: f["resultado"] for f in final["trazabilidad"]}
    assert resultados == {
        "A-0082": "error_normalizacion",
        "A-0015": "rechazado_localmente",
        "A-0001": "aceptado",
    }


def test_normalizadas_incluye_los_rechazados_localmente():
    normalizados, _, _, _, _, _ = _escenario()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = reporte.guardar_normalizadas(carpeta, normalizados)
        import json
        contenido = json.load(open(ruta, encoding="utf-8"))
    assert len(contenido) == 2
    estados = {r["id_trazabilidad"]: r["estado_validacion"] for r in contenido}
    assert estados["A-0015"] == "rechazado_localmente"
    # El archivo de evidencia conserva el contrato completo por registro.
    assert sorted(contenido[0]["medicion"].keys()) == sorted(medicion_valida().keys())
