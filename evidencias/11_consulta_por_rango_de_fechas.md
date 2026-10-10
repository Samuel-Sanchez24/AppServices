# Prueba 11 — Consulta por rango de fechas

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
`desde=2026-10-10T17:46:10Z` y `hasta=2026-10-10T17:48:20Z` (UTC), que equivalen a 2026-10-10T12:46:10-05:00 y 2026-10-10T12:48:20-05:00 en Colombia.

## Resultado obtenido
```http
GET /sensores/7/mediciones?desde=2026-10-10T17%3A46%3A10Z&hasta=2026-10-10T17%3A48%3A20Z
```

Respuesta **HTTP 200**:

```json
[
  {
    "id": 104030,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 20.91,
    "timestamp_local": "2026-10-10T12:48:20-05:00",
    "fecha_recepcion_local": "2026-10-10T12:48:20-05:00"
  },
  {
    "id": 104029,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 21,
    "magnitud": "h2s",
    "unidad": "ppm",
    "valor": 0.78,
    "timestamp_local": "2026-10-10T12:48:20-05:00",
    "fecha_recepcion_local": "2026-10-10T12:48:20-05:00"
  },
  {
    "id": 104025,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 30.11,
    "timestamp_local": "2026-10-10T12:48:15-05:00",
    "fecha_recepcion_local": "2026-10-10T12:48:15-05:00"
  },
  "... (47 elementos más)"
]
```

Filas devueltas: **50**; esperadas según la base: **50** (del total de 102). Todas dentro del rango: **sí**.

## Código HTTP
**200 OK**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `listar_mediciones_del_sensor` / `_fecha_o_422`
- `app/core/tiempo.py` → `parsear_filtro_fecha`
- `app/crud/medicion.py` → `listar_por_sensor` (filtros `desde`/`hasta`)

## Explicación
`desde` y `hasta` son inclusivos. Con zona horaria (`Z` o `-05:00`) se respetan; sin zona se interpretan como hora de Colombia; solo con fecha abarcan el día completo.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
