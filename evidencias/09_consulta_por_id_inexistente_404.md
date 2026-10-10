# Prueba 9 — Consulta por ID inexistente

**Estado:** OK · **Generado:** 2026-10-10 12:49:30-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
`id` inexistente: `1104134`.

## Resultado obtenido
```http
GET /mediciones/1104134
```

Respuesta **HTTP 404**:

```json
{
  "detail": "No existe una medición con id 1104134"
}
```

## Código HTTP
**404 Not Found**

## Registro almacenado o rechazado
No aplica: consulta de solo lectura (GET).

## Archivo y función donde se implementa
- `app/api/medicion.py` → `obtener_medicion` (lanza `HTTPException(404)` si `crud.obtener` devuelve `None`)

## Explicación
Un `id` con formato válido pero que no existe responde 404 con un mensaje claro.

## Observaciones
- Las consultas se ejecutaron contra el servidor HTTP en http://127.0.0.1:8000.
