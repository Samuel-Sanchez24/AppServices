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

ORIGEN_PROVEEDOR_A = "proveedor_a"
ORIGEN_PROVEEDOR_B = "proveedor_b"
ORIGENES_PERMITIDOS = (ORIGEN_PROVEEDOR_A, ORIGEN_PROVEEDOR_B)

RANGO_LATITUD = (-90.0, 90.0)
RANGO_LONGITUD = (-180.0, 180.0)
RANGO_HUMEDAD = (0.0, 100.0)
VIENTO_MINIMO = 0.0

HTTP_ACEPTADO = 201
HTTP_RECHAZO = (400, 409, 422)
HTTP_TRANSITORIO = (500, 503)

RUTA_MEDICIONES = "/api/v1/mediciones"


def cuerpo_api(medicion):
    return {campo: medicion[campo] for campo in CAMPOS_CONTRATO}
