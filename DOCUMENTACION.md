# Documentación técnica del integrador

Cliente integrador en Python que lee los datasets de dos proveedores meteorológicos, los adapta
al contrato institucional, los valida y los registra en la API del docente mediante HTTP.

## Estructura

```text
proyecto/
├── integrador.py            # Punto de entrada: constantes URL_BASE / EQUIPO y orquestación
├── integracion/
│   ├── contrato.py          # Contrato institucional: campos, rangos, origenes, rutas, body
│   ├── errores.py           # ErrorNormalizacion, ErrorLectura
│   ├── lectura.py           # Lectura tolerante de JSON y CSV (no modifica los originales)
│   ├── normalizacion.py     # Conversión de tipos, unidades y fechas al contrato
│   ├── validacion.py        # Reglas de negocio locales y clasificación
│   ├── cliente_api.py       # POST/GET, interpretación de códigos y reintentos
│   └── reporte.py           # salida/normalizadas.json y salida/reporte.json
├── datos/                   # Datasets suministrados (solo lectura)
├── salida/                  # Evidencias generadas por la ejecución
├── tests/                   # Pruebas automatizadas (no tocan la API real)
├── ANALISIS.md              # Análisis de contratos, decisiones y evidencia de ejecución
├── conftest.py  pytest.ini  # Configuración de pytest
└── requirements.txt
```

Cada módulo tiene una sola responsabilidad y sólo depende de los anteriores: `lectura` no conoce
el contrato, `normalizacion` no conoce HTTP y `cliente_api` no conoce los proveedores.

## Configuración y ejecución

1. Instalar dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. Editar las dos constantes al inicio de `integrador.py` con los datos del docente:

   ```python
   URL_BASE = "https://…"     # URL base de la API
   EQUIPO   = "…"             # Identificador de equipo
   ```

3. Ejecutar:

   ```bash
   python integrador.py
   ```

4. Pruebas:

   ```bash
   pytest
   ```

Las rutas de datos y de salida también son constantes (`RUTA_PROVEEDOR_A`, `RUTA_PROVEEDOR_B`,
`DIRECTORIO_SALIDA`) y se resuelven respecto a la carpeta del proyecto, de modo que el programa
funciona ejecutado desde cualquier directorio.

## Flujo de ejecución

| Etapa | Módulo | Qué produce |
|---|---|---|
| 1. Lectura | `lectura` | registros crudos de A y B; un dataset ilegible no detiene el otro |
| 2. Normalización | `normalizacion` | registros en el contrato + lista de errores de normalización |
| 3. Validación local | `validacion` | separación en válidos y `rechazado_localmente` |
| 4. Evidencia | `reporte` | `salida/normalizadas.json` (todos los normalizados) |
| 5. Integración HTTP | `cliente_api` | un resultado por registro enviado |
| 6. Consulta | `cliente_api` | `GET …?equipo=<EQUIPO>` |
| 7. Reporte | `reporte` | `salida/reporte.json` con conteos, detalle y trazabilidad |

## Clasificación de cada registro

| Estado | ¿Se envía? | ¿Está en `normalizadas.json`? | ¿Está en el reporte? |
|---|:--:|:--:|:--:|
| `error_normalizacion` | no | no | sí (`detalle.errores_normalizacion`) |
| `rechazado_localmente` | no | sí | sí (`detalle.rechazados_localmente`) |
| `aceptado` (`201`) | sí | sí | sí |
| `rechazado_api` (`4xx`) | sí | sí | sí (con cuerpo de la respuesta) |
| `error_comunicacion` (`5xx`, timeout, red) | sí (hasta 3 intentos) | sí | sí |

## Política de reintentos

`cliente_api.ClienteMediciones.registrar` realiza 1 intento inicial y hasta 2 reintentos
(3 como máximo por registro), con espera incremental de 1 s y 2 s, **únicamente** ante `5xx`,
timeout o pérdida de conexión. Toda respuesta `4xx` es definitiva y no se reintenta. Un `2xx`
distinto de `201` o un `3xx` se registran como respuesta inesperada, sin reintento. Las
excepciones de `requests` nunca se propagan: se convierten en un resultado con estado
`error_comunicacion`.

## Trazabilidad

Cada registro conserva `id_trazabilidad`: el identificador del proveedor
(`provider_record_id` / `record_code`) o, si falta, uno derivado de la fuente y la posición
(`proveedor_a#7`). Se usa sólo en evidencias y reporte; `contrato.cuerpo_api` garantiza que el
body enviado contenga exclusivamente los nueve campos del contrato.

## Manejo de errores

| Situación | Tratamiento |
|---|---|
| Archivo inexistente / JSON no interpretable / CSV vacío | `ErrorLectura`, mensaje en consola, el dataset queda en 0 registros |
| Fila CSV con columnas faltantes o sobrantes | se marca `_fila_defectuosa` y se clasifica como error de normalización |
| Valor no convertible, nulo o fecha inválida | `ErrorNormalizacion` con campo, valor y motivo |
| Timeout / pérdida de conexión / `5xx` | reintentos controlados y estado `error_comunicacion` |
| Respuesta no JSON | se guarda un recorte del texto en `_respuesta_no_json` |
| Cualquier excepción no prevista | capturada en `main()`; el programa termina con código 1 y mensaje, nunca con traceback |

## Pruebas automatizadas

32 pruebas en `tests/`, todas aisladas de la API real mediante una sesión falsa
(`tests/dobles.py`), sin acceso a red:

| Archivo | Cubre |
|---|---|
| `test_normalizacion.py` | transformación correcta de A y B, conversión de unidades, fechas ISO 8601, los cuatro tipos de error de normalización, identificador derivado |
| `test_validacion.py` | registro válido, registro inválido, **casos límite** (0 y 100 de humedad, viento 0, latitud ±90, longitud ±180 y un paso fuera) |
| `test_cliente_api.py` | `201`; `400`/`409`/`422`/`404` sin reintento; `5xx` y timeout agotando 3 intentos; `5xx` seguido de `201`; respuesta no JSON; código inesperado; headers, ruta y body sin `id_trazabilidad`; `GET` con `equipo` |
| `test_lectura.py` | archivo inexistente, JSON inválido, fila CSV defectuosa, lectura completa de los 400 registros |
| `test_reporte.py` | los conteos cuadran, `normalizadas.json` conserva los rechazados localmente |
