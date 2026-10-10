# Prueba 16 — Filtro por magnitud

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
`magnitud=temperature` sobre el sensor `GAS-004`.

## Resultado obtenido
```http
GET /sensores/7/mediciones?magnitud=temperature
```

Respuesta **HTTP 200**:

```json
[
  {
    "id": 104139,
    "sensor_id": 7,
    "sensor_codigo": "GAS-004",
    "sensor_magnitud_id": 20,
    "magnitud": "temperature",
    "unidad": "C",
    "valor": 20.3,
    "timestamp_local": "2026-10-10T12:49:30-05:00",
    "fecha_recepcion_local": "2026-10-10T12:49:30-05:00"
  },
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
  "... (49 elementos más)"
]
```

Filas devueltas: **52**, todas con `magnitud = temperature` (en la base había 51 al iniciar).

Magnitud que el sensor no tiene:

```http
GET /sensores/7/mediciones?magnitud=magnitud_inexistente
```

Respuesta **HTTP 404**:

```json
{
  "detail": "El sensor 'GAS-004' no tiene la magnitud 'magnitud_inexistente'"
}
```

## Código HTTP
**200 OK** (filtro válido) y **404** (magnitud inexistente)

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `listar_mediciones_del_sensor` (parámetro `magnitud`)
- `app/crud/medicion.py` → `listar_por_sensor` (JOIN con `sensor_magnitudes`)

## Explicación
El filtro se resuelve con un JOIN a `sensor_magnitudes`. Una magnitud que el sensor no tiene responde 404.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
