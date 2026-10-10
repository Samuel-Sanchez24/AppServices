# Prueba 17 — Claves foráneas

**Estado:** OK · **Generado:** 2026-10-10 12:49:31-05:00 (hora de Colombia) por `scripts/generar_evidencias.py`

## Datos de entrada
Inspección del esquema real de PostgreSQL y una inserción deliberadamente errónea (dentro de una transacción que se revierte).

## Resultado obtenido
Claves foráneas definidas en PostgreSQL:

```json
{
  "sensor_magnitudes": [
    {
      "nombre": "fk_magnitud_sensor",
      "columnas": [
        "sensor_id"
      ],
      "referencia": "sensores(id)",
      "opciones": {
        "onupdate": "CASCADE",
        "ondelete": "RESTRICT"
      }
    }
  ],
  "mediciones": [
    {
      "nombre": "fk_medicion_magnitud",
      "columnas": [
        "sensor_magnitud_id"
      ],
      "referencia": "sensor_magnitudes(id)",
      "opciones": {
        "onupdate": "CASCADE",
        "ondelete": "RESTRICT"
      }
    }
  ]
}
```

Recorrido por el ORM (relationships):

```text
medición 104139 -> sensor_magnitud 20 (temperature, C) -> sensor 7 (GAS-004)
```

Mediciones huérfanas (sin magnitud asociada): **0**

Intento de insertar una medición con `sensor_magnitud_id = 2000000000` (no existe):

```text
ForeignKeyViolation: insert or update on table "mediciones" violates foreign key constraint "fk_medicion_magnitud"
```

## Código HTTP
No aplica: verificación del esquema y de las relaciones en la base de datos.

## Registro almacenado o rechazado
RECHAZADO por la base de datos (violación de clave foránea); la transacción se revirtió, no queda nada guardado.

## Archivo y función donde se implementa
- `app/models/sensor_magnitud.py` → `SensorMagnitud.sensor_id` (`ForeignKey('sensores.id')`)
- `app/models/medicion.py` → `Medicion.sensor_magnitud_id` (`ForeignKey('sensor_magnitudes.id')`)
- `app/models/*.py` → `relationship()` entre las tres entidades

## Explicación
El modelo ORM reproduce las dos relaciones 1:N de `data-model.md`. PostgreSQL las hace cumplir (`ON UPDATE CASCADE ON DELETE RESTRICT`): no se puede insertar una medición de una magnitud inexistente ni borrar una magnitud con histórico.
