# Prueba 12 — Rango con desde > hasta

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
`desde=2026-10-10T17:48:20Z` es posterior a `hasta=2026-10-10T17:46:10Z`.

## Resultado obtenido
```http
GET /sensores/7/mediciones?desde=2026-10-10T17%3A48%3A20Z&hasta=2026-10-10T17%3A46%3A10Z
```

Respuesta **HTTP 400**:

```json
{
  "detail": "El parámetro 'desde' no puede ser posterior a 'hasta'"
}
```

## Código HTTP
**400 Bad Request**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `listar_mediciones_del_sensor` (lanza `HTTPException(400)`)

## Explicación
Si `desde` es posterior a `hasta` la consulta es contradictoria y se responde 400 antes de consultar la base.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
