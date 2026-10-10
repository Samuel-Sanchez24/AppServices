# Prueba 8 — Consulta por ID existente

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Medición existente con id `104134` (la más reciente del sensor `GAS-004`).

## Resultado obtenido
```http
GET /mediciones/104134
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

Conversión verificada: en la base `timestamp_utc` = `2026-10-10T17:49:25+00:00`; la respuesta muestra `2026-10-10T12:49:25-05:00` (UTC-05:00).

## Código HTTP
**200 OK**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `obtener_medicion`
- `app/crud/medicion.py` → `obtener`
- `app/schemas/medicion.py` → `MedicionOut.desde_orm` (conversión a hora de Colombia)

## Explicación
Se consulta una medición real por su `id`. La respuesta incluye la magnitud, la unidad y el sensor (por las claves foráneas) y muestra el instante en hora de Colombia, aunque en la base se guarda en UTC.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
