# Prueba extra — Validaciones adicionales (rango, todo o nada, sensor ajeno, timestamp futuro)

**Estado:** OK · **Generado:** 2026-10-10 12:49:28-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Cuatro mensajes inválidos adicionales (detallados abajo).

## Resultado obtenido
### A. Valor fuera de rango — OK

Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — `temperature` supera `valor_maximo` (50.0000).

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "temperature": {
      "value": 91.0,
      "unit": "C"
    },
    "h2s": {
      "value": 2.161,
      "unit": "ppm"
    }
  }
}
```

Resultado del procesamiento:

```text
RECHAZADO | motivo=VALOR_FUERA_DE_RANGO | 'temperature': valor 91.0 fuera del rango permitido [10.0000, 50.0000] C
```

Motivo esperado: `VALOR_FUERA_DE_RANGO` · obtenido: `VALOR_FUERA_DE_RANGO`.

### B. Todo o nada — OK

Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — `temperature` es válida pero `h2s` trae una unidad incorrecta: no se debe guardar ninguna.

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "temperature": {
      "value": 27.2879,
      "unit": "C"
    },
    "h2s": {
      "value": 2.161,
      "unit": "unidad-incorrecta"
    }
  }
}
```

Resultado del procesamiento:

```text
RECHAZADO | motivo=UNIDAD_INCORRECTA | 'h2s': unidad 'unidad-incorrecta' distinta de la esperada 'ppm'
```

Motivo esperado: `UNIDAD_INCORRECTA` · obtenido: `UNIDAD_INCORRECTA`.

### C. Sensor de otro grupo — OK

Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — el sensor `AQ-001` existe, pero no es el asignado (`GAS-004`).

```json
{
  "sensor_id": "AQ-001",
  "timestamp": "2026-01-01T00:00:00Z",
  "measurements": {
    "co2": {
      "value": 2331.3306,
      "unit": "ppm"
    },
    "humidity": {
      "value": 43.2198,
      "unit": "%"
    },
    "temperature": {
      "value": 25.1269,
      "unit": "C"
    }
  }
}
```

Resultado del procesamiento:

```text
RECHAZADO | motivo=SENSOR_NO_ASIGNADO | El payload es del sensor 'AQ-001' pero llegó por el tópico 'iot/sensors/GAS-004/data'; solo se almacenan datos del sensor asignado
```

Motivo esperado: `SENSOR_NO_ASIGNADO` · obtenido: `SENSOR_NO_ASIGNADO`.

### D. Timestamp en el futuro — OK

Mensaje de prueba entregado a `procesar_mensaje` como si llegara por `iot/sensors/GAS-004/data` (la misma función que invoca el consumidor MQTT) — el timestamp es de mañana.

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-11T17:49:28Z",
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

Resultado del procesamiento:

```text
RECHAZADO | motivo=TIMESTAMP_INVALIDO | timestamp en el futuro (2026-10-11T17:49:28+00:00); tolerancia 600 s
```

Motivo esperado: `TIMESTAMP_INVALIDO` · obtenido: `TIMESTAMP_INVALIDO`.

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
**A.** **RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

Durante la captura, el consumidor rechazó **1** mensaje(s) reales por `VALOR_FUERA_DE_RANGO`. Ejemplo tomado de `logs/app.log`:

```text
2026-10-10 12:46:20 | WARNING  | app.mqtt | RECHAZADO | motivo=VALOR_FUERA_DE_RANGO | 'temperature': valor 999999.0 fuera del rango permitido [10.0000, 50.0000] C
```

**B.** **RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `UNIDAD_INCORRECTA` durante la captura.

**C.** **RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `SENSOR_NO_ASIGNADO` durante la captura.

Filas con el timestamp de prueba en cualquier sensor: **0**.

**D.** **RECHAZADO**. Filas insertadas en `mediciones` con los datos de esta prueba: **0** (la prueba se ejecuta en una transacción que se revierte, no deja nada en la base).

En `logs/app.log` no hay mensajes reales rechazados por `TIMESTAMP_INVALIDO` durante la captura.

## Archivo y función donde se implementa
- `app/services/ingesta.py` → `procesar_mensaje` (pasos 3, 4 y 5)

## Explicación
Reglas que van más allá de la lista mínima de la guía: el valor debe estar dentro de `valor_minimo`/`valor_maximo`; si una magnitud es inválida no se guarda ninguna del mismo payload; solo se almacenan datos del sensor asignado (no se tocan datos de otros grupos); y un timestamp futuro se considera inválido.
