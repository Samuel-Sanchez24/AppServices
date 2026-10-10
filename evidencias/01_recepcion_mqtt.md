# Prueba 1 — Recepción MQTT desde el tópico asignado

**Estado:** OK · **Generado:** 2026-10-10 12:49:25-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Tópico suscrito: `iot/sensors/GAS-004/data`.

## Resultado obtenido
Ventana de ejecución registrada: 2026-10-10 12:45:02 a 2026-10-10 12:49:25 (hora local del equipo).

- Mensajes recibidos: **53**
- Almacenados: **51**
- Rechazados: **2**

| Motivo de rechazo | Cantidad |
|---|---|
| `TIPO_DATO_INVALIDO` | 1 |
| `VALOR_FUERA_DE_RANGO` | 1 |

Primer mensaje recibido (extracto de `logs/app.log`):

```text
2026-10-10 12:45:04 | INFO     | app.mqtt | MENSAJE RECIBIDO | topico=iot/sensors/GAS-004/data | payload={"sensor_id": "GAS-004", "timestamp": "2026-10-10T17:45:05Z", "measurements": {"h2s": {"value": 0.9, "unit": "ppm"}, "temperature": {"value": 29.34, "unit": "C"}}}
```

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
Los mensajes aceptados y rechazados quedan en `logs/app.log` (ver pruebas 2 a 7).

## Archivo y función donde se implementa
- `app/mqtt/client.py` → `ClienteMQTT._al_conectar` (suscripción al tópico asignado, QoS 1)
- `app/mqtt/client.py` → `ClienteMQTT._al_recibir` (recepción y registro de cada mensaje)

## Explicación
El consumidor se conecta al broker, se suscribe únicamente al tópico del sensor asignado y registra cada mensaje recibido. La captura inicial de mensajes reales (con el análisis de su estructura) está en `00_captura_mqtt_inicial.md`; aquí se resume lo que registró la aplicación durante toda la ejecución.

## Observaciones
- Captura de mensajes reales con su análisis: `00_captura_mqtt_inicial.md`.
