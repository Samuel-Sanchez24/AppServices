# Prueba 14 — Última medición

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Sensor `GAS-004`. En la base la medición más reciente es la `104134` (2026-10-10T17:49:25+00:00 UTC).

## Resultado obtenido
```http
GET /sensores/7/ultima-medicion
```

Respuesta **HTTP 200**:

```json
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
}
```

Variante por magnitud:

```http
GET /sensores/7/ultima-medicion?magnitud=temperature
```

Respuesta **HTTP 200**:

```json
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
}
```

## Código HTTP
**200 OK**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `obtener_ultima_medicion`
- `app/crud/medicion.py` → `ultima_por_sensor`

## Explicación
Devuelve el registro con el `timestamp_utc` más reciente del sensor (desempata por `id`). Con `?magnitud=` devuelve la última de esa magnitud.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
