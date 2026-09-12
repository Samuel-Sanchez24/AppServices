"""Definición del contrato institucional.

Este módulo es la única fuente de verdad sobre los nombres de campo, los
tipos y las restricciones exigidas por `CONTRATO_API.md`. El resto del
programa no debe redefinir estas reglas.
"""

# Campos exigidos por el contrato, en el orden en que se documentan.
CAMPOS_CONTRATO = (
    "ciudad",
    "pais",
    "latitud",
    "longitud",
    "temperatura_c",
    "humedad",
    "viento_kmh",
    "fecha_hora",
    "origen",
)

# Valores institucionales permitidos para `origen`.
ORIGEN_PROVEEDOR_A = "proveedor_a"
ORIGEN_PROVEEDOR_B = "proveedor_b"
ORIGENES_PERMITIDOS = (ORIGEN_PROVEEDOR_A, ORIGEN_PROVEEDOR_B)

# Rangos numéricos del contrato.
RANGO_LATITUD = (-90.0, 90.0)
RANGO_LONGITUD = (-180.0, 180.0)
RANGO_HUMEDAD = (0.0, 100.0)
VIENTO_MINIMO = 0.0

# Códigos HTTP documentados en el contrato.
HTTP_ACEPTADO = 201
HTTP_RECHAZO = (400, 409, 422)
HTTP_TRANSITORIO = (500, 503)

# Rutas del contrato.
RUTA_MEDICIONES = "/api/v1/mediciones"


def cuerpo_api(medicion):
    """Devuelve el body a enviar a la API.

    Filtra cualquier campo interno (por ejemplo el identificador de
    trazabilidad): al servidor sólo viajan los campos del contrato.
    """
    return {campo: medicion[campo] for campo in CAMPOS_CONTRATO}
