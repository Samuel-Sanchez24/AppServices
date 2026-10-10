# Prueba 7 — Timestamp inválido

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — `timestamp` no es una fecha ISO 8601.

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "no-es-una-fecha",
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
RECHAZADO | motivo=TIMESTAMP_INVALIDO | timestamp: Value error, formato no reconocido; use ISO 8601, por ejemplo 2026-10-07T16:25:30Z
```

Motivo esperado: `TIMESTAMP_INVALIDO` · obtenido: `TIMESTAMP_INVALIDO`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `TIMESTAMP_INVALIDO` durante la captura.

## Archivo y función donde se implementa
- `app/schemas/medicion.py` → `_validar_timestamp` (validador del campo `timestamp`)
- `app/core/tiempo.py` → `parsear_timestamp_mqtt`

## Explicación
El timestamp debe ser ISO 8601 completo y con zona horaria (por ejemplo `2026-10-07T16:25:30Z`); se normaliza a UTC. Los valores inexistentes (`2026-13-45T...`), sin zona o numéricos también se rechazan (ver `tests/`).
