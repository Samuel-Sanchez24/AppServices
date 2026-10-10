# Prueba 5 — Tipo de dato incorrecto

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — `value` de `temperature` es texto en lugar de número.

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "temperature": {
      "value": "abc",
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
RECHAZADO | motivo=TIPO_DATO_INVALIDO | measurements.temperature.value: Input should be a valid number
```

Motivo esperado: `TIPO_DATO_INVALIDO` · obtenido: `TIPO_DATO_INVALIDO`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

Durante la captura, el consumidor rechazó **1** mensaje(s) reales por `TIPO_DATO_INVALIDO`. Ejemplo tomado de `logs/app.log`:

```text
2026-10-10 12:47:54 | WARNING  | app.mqtt | RECHAZADO | motivo=TIPO_DATO_INVALIDO | measurements.temperature.value: Input should be a valid number
```

## Archivo y función donde se implementa
- `app/schemas/medicion.py` → `MagnitudMQTT` (modelo Pydantic estricto: `value: float`)
- `app/services/ingesta.py` → `_clasificar_errores_pydantic`

## Explicación
Pydantic valida los tipos antes de tocar la base de datos. El modo estricto impide que se acepte `"412.5"`, `true` o `null` como número.
