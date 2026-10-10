# Prueba 6 — Magnitud incorrecta

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — se reemplazó la magnitud `temperature` por `magnitud_inexistente`.

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "h2s": {
      "value": 2.161,
      "unit": "ppm"
    },
    "magnitud_inexistente": {
      "value": 27.2879,
      "unit": "C"
    }
  }
}
```

## Resultado obtenido
Resultado del procesamiento:

```text
RECHAZADO | motivo=MAGNITUD_INVALIDA | La magnitud 'magnitud_inexistente' no está asociada al sensor GAS-004 (válidas: h2s, temperature)
```

Motivo esperado: `MAGNITUD_INVALIDA` · obtenido: `MAGNITUD_INVALIDA`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `MAGNITUD_INVALIDA` durante la captura.

## Archivo y función donde se implementa
- `app/services/ingesta.py` → `procesar_mensaje` (paso 5: relación sensor-magnitud)
- `app/crud/sensor_magnitud.py` → `listar_por_sensor`

## Explicación
Solo se aceptan las magnitudes asociadas al sensor en `sensor_magnitudes`.
