# Prueba 3 — Sensor inexistente

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — `sensor_id` que no existe en la tabla `sensores`.

```json
{
  "sensor_id": "NO-EXISTE-999",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "temperature": {
      "value": 27.2879,
      "unit": "C"
    },
    "h2s": {
      "value": 2.161,
      "unit": "ppm"
    }
  }
}
```

## Resultado obtenido
Resultado del procesamiento:

```text
RECHAZADO | motivo=SENSOR_INEXISTENTE | El sensor 'NO-EXISTE-999' no existe en el catálogo
```

Motivo esperado: `SENSOR_INEXISTENTE` · obtenido: `SENSOR_INEXISTENTE`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `SENSOR_INEXISTENTE` durante la captura.

## Archivo y función donde se implementa
- `app/services/ingesta.py` → `procesar_mensaje` (paso 4: sensor existente)
- `app/crud/sensor.py` → `obtener_por_codigo`

## Explicación
Tras validar la estructura, la aplicación busca el sensor por `codigo` mediante el ORM. Si no existe, el mensaje se descarta y nada se escribe.
