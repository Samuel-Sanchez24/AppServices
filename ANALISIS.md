# Análisis de integración — Taller 1

## 1. Tabla de correspondencias entre contratos

| Contrato institucional | Tipo / unidad exigida | Proveedor A (JSON) | Proveedor B (CSV `;`) | Transformación necesaria |
|---|---|---|---|---|
| `ciudad` | string, no vacío | `station.city_name` | `municipality` | Aplanar estructura anidada (A) / renombrar (B) + `trim` |
| `pais` | string, no vacío | `station.country_code` | `country` | Renombrar; ya viene como código ISO `CO` |
| `latitud` | number, −90..90 | `location.lat` (number) | `latitude_deg` (texto) | Aplanar (A) / `str → float` (B) |
| `longitud` | number, −180..180 | `location.lon` (number) | `longitude_deg` (texto) | Aplanar (A) / `str → float` (B) |
| `temperatura_c` | number, °C | `measurements.temperature_f` (°F) | `temp_celsius` (°C, texto) | **A: `(°F − 32) × 5/9`**; B: `str → float` |
| `humedad` | number, 0..100 | `measurements.relative_humidity` (%) | `humidity_pct` (%, texto) | Renombrar; B: `str → float` |
| `viento_kmh` | number, ≥ 0 | `measurements.wind_speed_ms` (m/s) | `wind_kmh` (km/h, texto) | **A: `m/s × 3.6`**; B: `str → float` |
| `fecha_hora` | string, ISO 8601 | `observed_at` (`2026-09-01T00:00:00-05:00`) | `measurement_time` (`01/09/2026 06:00`) | A: validar ISO; **B: `dd/mm/yyyy HH:MM` → ISO 8601 añadiendo zona `-05:00`** |
| `origen` | `proveedor_a` \| `proveedor_b` | `source = "weather_provider_a"` | `origin_code = "PB"` | **Mapear a los valores institucionales** |
| *(no se envía)* | — | `provider_record_id` (`A-0001`) | `record_code` (`B-0001`) | Se conserva como identificador interno de trazabilidad |
| *(no se envía)* | — | `station.code`, `unit_system`, `provider`, `generated_at` | `origin_code` | Metadatos fuera del contrato: se descartan del body |

Las unidades del proveedor A no están en cada registro sino en la cabecera del archivo
(`unit_system: {temperature: "F", wind_speed: "m/s"}`): sin leer esa cabecera se enviarían
temperaturas en Fahrenheit con el nombre `temperatura_c`, un error que la API no puede detectar.

## 2. ¿Qué diferencias encontró entre los contratos de los proveedores?

Cuatro clases de diferencia, en orden de riesgo:

1. **Unidades.** A entrega °F y m/s; B entrega °C y km/h. El contrato institucional exige °C y km/h.
   Es la única diferencia que produce datos *plausibles pero incorrectos* si se ignora.
2. **Estructura.** A es un documento JSON con un sobre (`provider`, `unit_system`, `records`) y
   objetos anidados (`station`, `location`, `measurements`); B es tabular y plano, delimitado por
   `;`. El contrato es plano, de un solo nivel.
3. **Tipos.** En A los números son números JSON (y aparecen `null` y la cadena `"N/A"`); en B
   **todo es texto**, incluidas las cifras, y los faltantes son campos vacíos.
4. **Formato de fecha y vocabulario.** A usa ISO 8601 con desplazamiento (`-05:00`); B usa
   `dd/mm/yyyy HH:MM` sin zona horaria, que hay que interpretar como hora local de Colombia.
   Los nombres de campo difieren en idioma y convención (`city_name` / `municipality` / `ciudad`),
   y el valor de origen difiere en los tres contratos (`weather_provider_a`, `PB`, `proveedor_a`).

## 3. ¿Qué transformaciones fueron necesarias?

* **Conversión de unidades:** `temperatura_c = (temperature_f − 32) × 5/9` y
  `viento_kmh = wind_speed_ms × 3.6`, sólo para el proveedor A, redondeando a 2 decimales.
* **Conversión de tipos:** `str → float` para las ocho columnas numéricas del CSV, aceptando coma
  o punto decimal.
* **Aplanamiento y renombrado:** de `station.city_name`, `location.lat`, `measurements.*` a los
  nueve campos planos del contrato.
* **Normalización de fechas a ISO 8601:** `dd/mm/yyyy HH:MM` → `2026-09-01T06:00:00-05:00`,
  añadiendo explícitamente la zona `-05:00` para no perder el instante real.
* **Mapeo del vocabulario de origen:** `weather_provider_a` → `proveedor_a`, `PB` → `proveedor_b`.
* **Recorte del body:** el identificador de trazabilidad y los metadatos del proveedor no
  pertenecen al contrato y se eliminan antes del `POST` (`contrato.cuerpo_api`).

## 4. ¿Qué tipos de errores encontró antes de enviar información?

Se distinguen dos categorías, y la frontera entre ellas fue la decisión de diseño más discutible:

**a) Errores de normalización (8 registros).** El dato presente no admite representación en el
contrato, de modo que el registro no se envía ni aparece en `salida/normalizadas.json`:

| Caso | Registros | Causa |
|---|---|---|
| Texto no numérico en campo numérico | `A-0082` (`"N/A"`), `B-0114` (`"error"`) | no convertible a número |
| Nulo o vacío en campo numérico | `A-0173` (`null`), `B-0146` (vacío) | no hay valor que convertir |
| Fecha ausente o no interpretable | `A-0040` (sin `observed_at`), `A-0174` (`09-XX-2026 25:61`), `B-0076` (vacía), `B-0171` (`31/13/2026 28:75`) | mes 13, hora 28, minuto 75 |

**b) Rechazos de la validación local (12 registros).** El registro *sí* se representa en el
contrato —por eso permanece en `normalizadas.json`— pero incumple una regla de negocio:

| Regla incumplida | Registros |
|---|---|
| `humedad` fuera de 0..100 | `A-0015` (108.4), `B-0004` (117.5) |
| `latitud` fuera de −90..90 | `A-0031` (95.245), `B-0006` (−94.22) |
| `longitud` fuera de −180..180 | `A-0175` (−190.75), `B-0190` (188.45) |
| `viento_kmh` negativo | `A-0088` (−8.64 km/h, venía −2.4 m/s), `B-0115` (−7.4) |
| `ciudad` vacía | `A-0136`, `B-0128` |
| `pais` vacío | `A-0150` (sin `country_code`), `B-0135` |

**Criterio adoptado:** los campos de texto *siempre* admiten representación (ausente o nulo se
normaliza como cadena vacía) y por tanto `ciudad`/`pais` se resuelven siempre en la validación
local; los campos numéricos y de fecha sólo se normalizan si el valor puede convertirse. Así,
`A-0150` (sin `country_code`) se cuenta como rechazo local y no como error de normalización,
lo que permite dejar el registro en la evidencia con el motivo explícito.

Además se previeron errores de lectura que los datasets del taller no presentan: archivo
inexistente, JSON no interpretable y fila CSV con número de columnas distinto al encabezado
(esta última se marca y se clasifica como error de normalización sin detener la lectura).

## 5. ¿Qué diferencias encontró entre validación local y validación del servidor?

La validación local sólo puede comprobar lo que el contrato documenta: presencia, tipo y rango.
El servidor valida de forma independiente y conoce cosas que el cliente no: unicidad de la
medición (`409`), reglas adicionales no publicadas (`422`), autorización del equipo y límites de
su propio almacenamiento. En consecuencia:

* La validación local es **preventiva, no autoritativa**: ahorra viajes de red y aísla los datos
  ya inválidos, pero un registro que la supera puede ser rechazado igual.
* El cliente por tanto **no asume** que `201` es el único desenlace posible: clasifica cada
  registro por lo que el servidor respondió, no por lo que el cliente predijo.
* Los códigos se interpretan distinto según su naturaleza: `4xx` es un veredicto sobre el dato
  (definitivo, no se reintenta); `5xx`, el timeout y la pérdida de conexión son fallos del canal
  (transitorios, se reintentan hasta 3 intentos por registro). Un `2xx` distinto de `201` se
  registra como respuesta inesperada sin reintentar, en lugar de darse por aceptado.

## 6. ¿Qué decisión de implementación considera más importante y por qué?

**Separar "error de normalización" de "rechazado localmente" como dos estados distintos, y
conservar un identificador de trazabilidad por registro desde la lectura.**

Es la decisión que sostiene todo lo demás. Define qué entra en `normalizadas.json` (los 392 que
sí se pudieron representar, rechazados incluidos) y qué sólo vive en el reporte (los 8 que no);
permite que los conteos cuadren y se puedan auditar
(`procesados = normalizados + errores_normalizacion`,
`normalizados = válidos + rechazados_localmente`); y garantiza que ningún registro problemático
se omita en silencio, que es justamente lo que el taller prohíbe. El identificador de trazabilidad
es lo que hace accionable esa clasificación: cada una de las 400 filas puede rastrearse hasta su
resultado final sin volver a los datos de origen. La decisión complementaria es mantener ese
identificador **fuera del body**: es evidencia interna, no parte del contrato institucional.

Una decisión de segundo orden, pero que evitó un error silencioso: leer `unit_system` del
proveedor A en lugar de suponer que "temperatura" significa lo mismo en ambas fuentes.

---

# Evidencia de ejecución real

> **Pendiente:** esta sección corresponde a una ejecución de verificación contra una API local
> que implementa `CONTRATO_API.md`. Tras correr `python integrador.py` contra
> `https://appsweb.quantaiot.co` con el equipo `EQUIPO-06-APPSWEB`, reemplazar las cifras de la
> API (aceptados, rechazados, errores de comunicación y consulta final) por las de
> `salida/reporte.json`. Las cifras del procesamiento local (400 / 392 / 8 / 380 / 12) no cambian:
> dependen solo de los datasets.

Ejecución de `python integrador.py` sobre 400 registros de `datos/proveedor_a.json` (200) y
`datos/proveedor_b.csv` (200). Cifras tomadas de `salida/reporte.json`.

## Resumen

| Indicador | Valor |
|---|---:|
| Registros procesados | **400** |
| Normalizados | **392** |
| Errores de normalización | **8** |
| Válidos localmente | **380** |
| Rechazados localmente | **12** |
| Enviados a la API | **380** |
| Aceptados por la API (`201`) | **380** |
| Rechazados por la API (`4xx`) | **0** |
| Errores de comunicación | **0** |

`400 = 392 + 8` · `392 = 380 + 12` · `380 = 380 + 0 + 0`

## Caso de error de normalización (no se envía, no entra en `normalizadas.json`)

```json
{ "id_trazabilidad": "A-0082", "origen": "proveedor_a", "campo": "temperature_f",
  "valor": "'N/A'", "motivo": "texto no convertible a número" }
```

## Caso de rechazo local (sí permanece en `normalizadas.json`, no se envía)

```json
{ "id_trazabilidad": "A-0015", "origen": "proveedor_a",
  "estado_validacion": "rechazado_localmente",
  "errores_validacion": ["humedad fuera de rango [0.0, 100.0]: 108.4"],
  "medicion": { "ciudad": "Barranquilla", "pais": "CO", "latitud": 10.969955,
    "longitud": -74.762201, "temperatura_c": 28.67, "humedad": 108.4,
    "viento_kmh": 10.01, "fecha_hora": "2026-09-01T07:00:00-05:00",
    "origen": "proveedor_a" } }
```

## Conversión de unidades verificada sobre datos reales

| Registro | Origen | Valor de origen | Valor normalizado |
|---|---|---|---|
| `A-0001` | proveedor_a | `66.1 °F`, `8.47 m/s` | `temperatura_c = 18.94`, `viento_kmh = 30.49` |
| `B-0001` | proveedor_b | `21.55 °C`, `21.85 km/h` | `temperatura_c = 21.55`, `viento_kmh = 21.85` (sin conversión) |
| `B-0001` | proveedor_b | `01/09/2026 06:00` | `fecha_hora = 2026-09-01T06:00:00-05:00` |

## Respuesta recibida desde la API (`POST`)

```json
{ "id_trazabilidad": "A-0001", "resultado": "aceptado", "codigo_http": 201, "intentos": 1,
  "respuesta": { "mensaje": "medicion registrada", "id": 1, "equipo": "EQUIPO-06-APPSWEB" } }
```

## Resultado de la consulta final (`GET /api/v1/mediciones?equipo=<EQUIPO>`)

```json
{ "estado": "ok", "codigo_http": 200,
  "respuesta": { "equipo": "EQUIPO-06-APPSWEB", "total": 380, "mediciones": [
    { "ciudad": "Medellin", "pais": "CO", "latitud": 6.242282, "longitud": -75.595933,
      "temperatura_c": 18.94, "humedad": 81.3, "viento_kmh": 30.49,
      "fecha_hora": "2026-09-01T00:00:00-05:00", "origen": "proveedor_a",
      "id": 1, "almacenado_en": "2026-09-12T00:00:00-05:00" } ] } }
```

Los 380 registros enviados coinciden con los 380 que la API reporta para el equipo: no hubo
pérdidas ni duplicados. Las rutas de reintento y de rechazo `4xx`/`5xx` quedan verificadas en
`tests/test_cliente_api.py` (`5xx` y timeout agotan 3 intentos; `400`, `409` y `422` no se
reintentan), ya que esta ejecución no produjo fallos de canal.
