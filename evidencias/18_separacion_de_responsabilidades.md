# Prueba 18 — Separación de responsabilidades

**Estado:** OK · **Generado:** 2026-10-10 12:49:31-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Revisión automática del código fuente de `app/` (existencia de archivos y reglas entre capas).

## Resultado obtenido
| Archivo | Existe | Responsabilidad |
|---|---|---|
| `app/main.py` | sí | Punto de entrada: crea la app FastAPI, registra los routers y arranca/detiene el consumidor MQTT (lifespan). |
| `app/database/connection.py` | sí | Engine, sesiones y clase base del ORM; dependencia `get_db`. |
| `app/models/sensor.py` | sí | Tabla `sensores` como clase ORM. |
| `app/models/sensor_magnitud.py` | sí | Tabla `sensor_magnitudes` (FK a sensores). |
| `app/models/medicion.py` | sí | Tabla `mediciones` (FK a sensor_magnitudes). |
| `app/schemas/sensor.py` | sí | Esquema Pydantic de respuesta de sensores. |
| `app/schemas/sensor_magnitud.py` | sí | Esquema Pydantic de respuesta de sensor-magnitudes. |
| `app/schemas/medicion.py` | sí | Esquemas Pydantic del payload MQTT (validación) y de la respuesta de mediciones. |
| `app/crud/sensor.py` | sí | Consultas de sensores (solo lectura). |
| `app/crud/sensor_magnitud.py` | sí | Consultas de sensor-magnitudes (solo lectura). |
| `app/crud/medicion.py` | sí | Inserción atómica y consultas de mediciones. |
| `app/services/ingesta.py` | sí | Reglas de negocio de la ingesta MQTT (validación en capas y almacenamiento). |
| `app/api/sensor.py` | sí | Endpoints HTTP de sensores. |
| `app/api/sensor_magnitud.py` | sí | Endpoints HTTP de sensor-magnitudes. |
| `app/api/medicion.py` | sí | Endpoints HTTP de mediciones. |
| `app/mqtt/client.py` | sí | Transporte MQTT: conexión, suscripción, reconexión y registro; delega en el servicio. |
| `app/core/config.py` | sí | Variables de entorno. |
| `app/core/tiempo.py` | sí | UTC <-> hora de Colombia y parseo de fechas. |

Reglas de dependencia entre capas (búsqueda de patrones prohibidos en el código):

| Carpeta | Regla | Resultado |
|---|---|---|
| `app/api/` | las rutas HTTP no escriben SQL: delegan en `crud/` | cumple |
| `app/mqtt/` | el cliente MQTT no accede a la base: delega en `services/` | cumple |
| `app/crud/` | `crud/` no conoce HTTP ni MQTT | cumple |
| `app/models/` | `models/` solo describe tablas | cumple |
| `app/schemas/` | `schemas/` solo valida/serializa datos | cumple |

## Código HTTP
No aplica.

## Registro almacenado o rechazado
No aplica.

## Archivo y función donde se implementa
- Estructura `app/` completa (ver tabla)
- `app/services/ingesta.py` (lógica de negocio separada del transporte MQTT y de HTTP)

## Explicación
Cada capa tiene una única responsabilidad y solo conoce a la inferior: `api`/`mqtt` -> `services`/`crud` -> `models`/`database`. Los esquemas Pydantic validan datos de entrada/salida y no tocan la base.
