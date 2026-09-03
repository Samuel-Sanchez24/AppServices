# Clase 03 — Transformación de datos: CSV a JSON

## Propósito

Practica el flujo completo de una aplicación que recibe datos externos (CSV), los interpreta como estructuras de Python, selecciona y transforma la información necesaria, y genera una representación (JSON) que otra aplicación podría consumir.

```
estudiantes.csv → estructuras de Python → transformación → estudiantes_resumen.json
```

## Estructura del proyecto

```
clase-03-datos/
├── datos/
│   └── estudiantes.csv
├── salida/
│   └── estudiantes_resumen.json
├── transformar_estudiantes.py
└── README.md
```

## Requisitos

- Python 3 instalado.
- Solo módulos de la biblioteca estándar: `csv`, `json`, `pathlib`. No requiere `pip install`.

## Cómo ejecutar

```
python transformar_estudiantes.py
```

El script:

1. Lee `datos/estudiantes.csv` con `csv.DictReader`.
2. Transforma cada registro al formato del panel académico (ver tabla abajo).
3. Serializa el resultado en `salida/estudiantes_resumen.json`.
4. Deserializa ese mismo JSON y muestra el primer registro recuperado y el total.

## Transformación aplicada

| Dato de entrada       | Dato de salida            |
|------------------------|----------------------------|
| `codigo`               | `id`                       |
| `nombre` + `apellido`  | `nombre_completo`          |
| `semestre` (texto)     | `semestre` (entero)        |
| `promedio` (texto)     | `promedio` (decimal)       |
| `activo` (true/false)  | `estado` (Activo/Inactivo) |
| `correo`               | no se incluye en la salida |

Cualquier otra columna del CSV (por ejemplo `programa`) se ignora: el script solo lee los campos que necesita, por nombre.
