# Prueba 15 — Últimas N mediciones (limit)

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
`limit=5` sobre el sensor `GAS-004`.

## Resultado obtenido
```http
GET /sensores/7/mediciones?limit=5
```

Respuesta **HTTP 200**:

```json
[
  {
    "id": 104134,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 28.13,
    "timestamp_local": "2026-10-10T12:49:25-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:25-05:00"
  },
  {
    "id": 104133,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 21,
    "magnitud": "h2s",
    "unidad": "ppm",
    "valor": 0.73,
    "timestamp_local": "2026-10-10T12:49:25-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:25-05:00"
  },
  {
    "id": 104126,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 19.15,
    "timestamp_local": "2026-10-10T12:49:20-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:20-05:00"
  },
  {
    "id": 104125,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 21,
    "magnitud": "h2s",
    "unidad": "ppm",
    "valor": 0.23,
    "timestamp_local": "2026-10-10T12:49:20-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:20-05:00"
  },
  {
    "id": 104118,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 26.34,
    "timestamp_local": "2026-10-10T12:49:15-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:15-05:00"
  }
]
```

Filas devueltas: **5**, de la más reciente a la más antigua.

## Código HTTP
**200 OK**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `listar_mediciones_del_sensor` (parámetro `limit`)
- `app/crud/medicion.py` → `listar_por_sensor` (`ORDER BY timestamp_utc DESC ... LIMIT n`)

## Explicación
`limit=N` devuelve únicamente las N mediciones más recientes (cada fila es una magnitud de un mensaje).

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
