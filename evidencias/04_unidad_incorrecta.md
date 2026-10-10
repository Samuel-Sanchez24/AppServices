# Prueba 4 — Unidad incorrecta

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — la unidad de `temperature` no coincide con `C` (la del catálogo).

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "temperature": {
      "value": 27.2879,
      "unit": "unidad-incorrecta"
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
RECHAZADO | motivo=UNIDAD_INCORRECTA | 'temperature': unidad 'unidad-incorrecta' distinta de la esperada 'C'
```

Motivo esperado: `UNIDAD_INCORRECTA` · obtenido: `UNIDAD_INCORRECTA`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `UNIDAD_INCORRECTA` durante la captura.

## Archivo y función donde se implementa
- `app/services/ingesta.py` → `procesar_mensaje` (paso 5: unidad)
- `app/crud/sensor_magnitud.py` → `listar_por_sensor`

## Explicación
Cada magnitud se compara con su configuración en `sensor_magnitudes`; la unidad debe ser exactamente la registrada.
