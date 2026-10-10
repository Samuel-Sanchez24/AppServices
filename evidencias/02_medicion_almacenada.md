# Prueba 2 — Medición válida almacenada en PostgreSQL

**Estado:** OK · **Generado:** 2026-10-10 12:49:25-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Mensajes reales publicados por el sensor `GAS-004` y procesados por la aplicación en ejecución (tópico `iot/sensors/GAS-004/data`).

## Resultado obtenido
- Filas almacenadas del sensor `GAS-004`: **102**
- Primera medición (UTC): 2026-10-10T17:45:05+00:00
- Última medición (UTC): 2026-10-10T17:49:25+00:00
- Ventana entre la primera y la última medición: 4.3 minutos
- Tramo continuo de captura más largo: **4.3 minutos** (la guía exige al menos 20)

Últimas filas en la tabla `mediciones` (valores tal como están en PostgreSQL):

| id | sensor_magnitud_id | magnitud | valor | timestamp_utc | fecha_recepcion |
|---|---|---|---|---|---|
| 104134 | 20 | `temperature` | 28.1300 C | 2026-10-10T17:49:25+00:00 | 2026-10-10T17:49:25.534345+00:00 |
| 104133 | 21 | `h2s` | 0.7300 ppm | 2026-10-10T17:49:25+00:00 | 2026-10-10T17:49:25.534345+00:00 |
| 104126 | 20 | `temperature` | 19.1500 C | 2026-10-10T17:49:20+00:00 | 2026-10-10T17:49:20.507003+00:00 |
| 104125 | 21 | `h2s` | 0.2300 ppm | 2026-10-10T17:49:20+00:00 | 2026-10-10T17:49:20.507003+00:00 |
| 104118 | 20 | `temperature` | 26.3400 C | 2026-10-10T17:49:15+00:00 | 2026-10-10T17:49:15.516162+00:00 |
| 104117 | 21 | `h2s` | 0.9700 ppm | 2026-10-10T17:49:15+00:00 | 2026-10-10T17:49:15.516162+00:00 |

Filas por magnitud:

| Magnitud | Filas |
|---|---|
| `h2s` | 51 |
| `temperature` | 51 |

Todas las magnitudes de un mismo mensaje comparten `timestamp_utc` (últimos 5 instantes y cuántas filas tiene cada uno):

| timestamp_utc | filas |
|---|---|
| 2026-10-10T17:49:25+00:00 | 2 |
| 2026-10-10T17:49:20+00:00 | 2 |
| 2026-10-10T17:49:15+00:00 | 2 |
| 2026-10-10T17:49:10+00:00 | 2 |
| 2026-10-10T17:49:05+00:00 | 2 |

## Código HTTP
No aplica: se procesa por MQTT (los errores se manejan internamente y se registran en el log).

## Registro almacenado o rechazado
ALMACENADO: 102 registros del sensor `GAS-004` en PostgreSQL. El log reporta 51 mensajes almacenados.

## Archivo y función donde se implementa
- `app/services/ingesta.py` → `procesar_mensaje` (paso 6: almacenamiento atómico)
- `app/crud/medicion.py` → `crear_varias` (una fila por magnitud, mismo `timestamp_utc`)
- `app/models/medicion.py` → `Medicion`

## Explicación
Cuando un mensaje supera todas las validaciones se inserta una fila en `mediciones` por cada magnitud del payload, todas con el mismo `timestamp_utc` y en una sola transacción. El instante se guarda en UTC; la columna `fecha_recepcion` la asigna PostgreSQL (`DEFAULT NOW()`).

## Observaciones
- ADVERTENCIA: el tramo continuo de captura es de 4.3 min; la guía pide al menos 20 min. Deja correr la aplicación más tiempo y vuelve a generar las evidencias.
