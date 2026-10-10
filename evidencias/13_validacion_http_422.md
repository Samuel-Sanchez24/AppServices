# Prueba 13 — Validación HTTP incorrecta

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Tres solicitudes con parámetros inválidos: id no numérico, `limit=0` y `desde` que no es fecha.

## Resultado obtenido
### Caso 1

```http
GET /sensores/abc
```

Respuesta **HTTP 422**:

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": [
        "path",
        "sensor_id"
      ],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc"
    }
  ]
}
```

### Caso 2

```http
GET /sensores/7/mediciones?limit=0
```

Respuesta **HTTP 422**:

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": [
        "query",
        "limit"
      ],
      "msg": "Input should be greater than or equal to 1",
      "input": "0",
      "ctx": {
        "ge": 1
      }
    }
  ]
}
```

### Caso 3

```http
GET /sensores/7/mediciones?desde=no-es-una-fecha
```

Respuesta **HTTP 422**:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "query",
        "desde"
      ],
      "msg": "Valor inválido para 'desde': formato no reconocido; use ISO 8601, por ejemplo 2026-10-07T16:25:30Z",
      "input": "no-es-una-fecha"
    }
  ]
}
```

## Código HTTP
**422 Unprocessable Entity** (en los tres casos)

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/dependencias.py` → `IdSensor` / `IdMedicion` (tipos de las rutas validados por FastAPI/Pydantic)
- `app/api/medicion.py` → `Query(ge=1)` en `limit` y `_fecha_o_422` para `desde`/`hasta`

## Explicación
FastAPI valida automáticamente los parámetros según su tipo y restricciones y responde 422 con el detalle del error.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
