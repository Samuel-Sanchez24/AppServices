# 00 — Captura inicial de mensajes MQTT del tópico asignado

**Generado:** 2026-10-10 12:43:21-05:00 (hora de Colombia) con `python -m scripts.verificar_conexiones`

| Dato | Valor |
|---|---|
| Broker | `emqx.coriotlab.co:1883` |
| Tópico suscrito | `iot/sensors/GAS-004/data` |
| Mensajes capturados | 5 |

## Estructura observada del payload
- `sensor_id` (texto): código del sensor, corresponde a `sensores.codigo`.
- `timestamp` (texto ISO 8601 en UTC). Ejemplos recibidos: `2026-10-10T17:43:00Z`, `2026-10-10T17:43:05Z`, `2026-10-10T17:43:10Z`
- `measurements` (objeto): una clave por magnitud, cada una con `value` (número) y `unit` (texto).

## Magnitudes, unidades y tipos observados
| Magnitud | Unidad(es) | Tipo de `value` | Rango de valores observado |
|---|---|---|---|
| `h2s` | 'ppm' | float | 0.1 a 0.99 |
| `temperature` | 'C' | float | 23.0 a 30.55 |

## Mensajes recibidos
### Mensaje 1

- Recibido: 2026-10-10 12:42:59-05:00 (hora de Colombia)
- Tópico: `iot/sensors/GAS-004/data`

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-10T17:43:00Z",
  "measurements": {
    "h2s": {
      "value": 0.27,
      "unit": "ppm"
    },
    "temperature": {
      "value": 24.8,
      "unit": "C"
    }
  }
}
```

Resultado de validarlo (simulación, sin escribir en la base): `VALIDO (simulacion: no se almacena) | sensor=GAS-004 | timestamp_utc=2026-10-10T17:43:00+00:00 | h2s=0.27 ppm, temperature=24.8 C`

### Mensaje 2

- Recibido: 2026-10-10 12:43:04-05:00 (hora de Colombia)
- Tópico: `iot/sensors/GAS-004/data`

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-10T17:43:05Z",
  "measurements": {
    "h2s": {
      "value": 0.88,
      "unit": "ppm"
    },
    "temperature": {
      "value": 23.62,
      "unit": "C"
    }
  }
}
```

Resultado de validarlo (simulación, sin escribir en la base): `VALIDO (simulacion: no se almacena) | sensor=GAS-004 | timestamp_utc=2026-10-10T17:43:05+00:00 | h2s=0.88 ppm, temperature=23.62 C`

### Mensaje 3

- Recibido: 2026-10-10 12:43:09-05:00 (hora de Colombia)
- Tópico: `iot/sensors/GAS-004/data`

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-10T17:43:10Z",
  "measurements": {
    "h2s": {
      "value": 0.96,
      "unit": "ppm"
    },
    "temperature": {
      "value": 25.73,
      "unit": "C"
    }
  }
}
```

Resultado de validarlo (simulación, sin escribir en la base): `VALIDO (simulacion: no se almacena) | sensor=GAS-004 | timestamp_utc=2026-10-10T17:43:10+00:00 | h2s=0.96 ppm, temperature=25.73 C`

### Mensaje 4

- Recibido: 2026-10-10 12:43:14-05:00 (hora de Colombia)
- Tópico: `iot/sensors/GAS-004/data`

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-10T17:43:15Z",
  "measurements": {
    "h2s": {
      "value": 0.1,
      "unit": "ppm"
    },
    "temperature": {
      "value": 30.55,
      "unit": "C"
    }
  }
}
```

Resultado de validarlo (simulación, sin escribir en la base): `VALIDO (simulacion: no se almacena) | sensor=GAS-004 | timestamp_utc=2026-10-10T17:43:15+00:00 | h2s=0.1 ppm, temperature=30.55 C`

### Mensaje 5

- Recibido: 2026-10-10 12:43:19-05:00 (hora de Colombia)
- Tópico: `iot/sensors/GAS-004/data`

```json
{
  "sensor_id": "GAS-004",
  "timestamp": "2026-10-10T17:43:20Z",
  "measurements": {
    "h2s": {
      "value": 0.99,
      "unit": "ppm"
    },
    "temperature": {
      "value": 23.0,
      "unit": "C"
    }
  }
}
```

Resultado de validarlo (simulación, sin escribir en la base): `VALIDO (simulacion: no se almacena) | sensor=GAS-004 | timestamp_utc=2026-10-10T17:43:20+00:00 | h2s=0.99 ppm, temperature=23.0 C`

**Implementación:** `app/mqtt/client.py` → `ClienteMQTT._al_conectar` (suscripción) y `ClienteMQTT._al_recibir` (recepción).
