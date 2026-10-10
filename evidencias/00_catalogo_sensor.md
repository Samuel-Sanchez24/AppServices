# 00 — Conexión a PostgreSQL y catálogo del sensor asignado

**Generado:** 2026-10-10 12:42:56-05:00 (hora de Colombia) con `python -m scripts.verificar_conexiones`

## Conexión
- Base de datos: `appdb` (el host y las credenciales se leen de `.env` y no se publican).
- Servidor: PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu
- Filas actuales: `sensores` = 25, `sensor_magnitudes` = 65, `mediciones` = 103755

## Sensor asignado
| id | codigo | nombre | categoria | ubicacion | activo |
|---|---|---|---|---|---|
| 7 | `GAS-004` | Sensor de sulfuro de hidrógeno | GAS | Planta de tratamiento | True |

## Magnitudes configuradas (`sensor_magnitudes`)
| id | magnitud | unidad | valor_minimo | valor_maximo |
|---|---|---|---|---|
| 20 | `temperature` | `C` | 10.0 | 50.0 |
| 21 | `h2s` | `ppm` | 0.0 | 5.0 |

Estas magnitudes, unidades y rangos son los que valida la aplicación al recibir cada mensaje.
