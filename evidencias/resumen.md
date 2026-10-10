# Resumen de evidencias

**Generado:** 2026-10-10 12:49:31-05:00 (hora de Colombia) con `python -m scripts.generar_evidencias`

| Dato | Valor |
|---|---|
| Sensor asignado | `GAS-004` (id 7) |
| Tópico MQTT | `iot/sensors/GAS-004/data` |
| Filas almacenadas en `mediciones` (una por magnitud) | 102 |
| Ventana de captura | tramo continuo de 4.3 min (NO cumple el mínimo de 20 min); entre la primera y la última medición: 4.3 min |

Archivos de apoyo: [00_catalogo_sensor.md](00_catalogo_sensor.md) (conexión a PostgreSQL y catálogo del sensor) y
[00_captura_mqtt_inicial.md](00_captura_mqtt_inicial.md) (mensajes reales recibidos y estructura del payload).
Registro de ejecución de la aplicación (consumidor MQTT): [registro_ejecucion.txt](registro_ejecucion.txt).

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
| 1 | Recepción MQTT desde el tópico asignado | OK | [01_recepcion_mqtt.md](01_recepcion_mqtt.md) |
| 2 | Medición válida almacenada en PostgreSQL | OK | [02_medicion_almacenada.md](02_medicion_almacenada.md) |
| 3 | Sensor inexistente | OK | [03_sensor_inexistente.md](03_sensor_inexistente.md) |
| 4 | Unidad incorrecta | OK | [04_unidad_incorrecta.md](04_unidad_incorrecta.md) |
| 5 | Tipo de dato incorrecto | OK | [05_tipo_dato_incorrecto.md](05_tipo_dato_incorrecto.md) |
| 6 | Magnitud incorrecta | OK | [06_magnitud_incorrecta.md](06_magnitud_incorrecta.md) |
| 7 | Timestamp inválido | OK | [07_timestamp_invalido.md](07_timestamp_invalido.md) |
| 8 | Consulta por ID existente | OK | [08_consulta_por_id_existente.md](08_consulta_por_id_existente.md) |
| 9 | Consulta por ID inexistente | OK | [09_consulta_por_id_inexistente_404.md](09_consulta_por_id_inexistente_404.md) |
| 10 | Consulta histórica | OK | [10_consulta_historica.md](10_consulta_historica.md) |
| 11 | Consulta por rango de fechas | OK | [11_consulta_por_rango_de_fechas.md](11_consulta_por_rango_de_fechas.md) |
| 12 | Rango con desde > hasta | OK | [12_rango_invalido_400.md](12_rango_invalido_400.md) |
| 13 | Validación HTTP incorrecta | OK | [13_validacion_http_422.md](13_validacion_http_422.md) |
| 14 | Última medición | OK | [14_ultima_medicion.md](14_ultima_medicion.md) |
| 15 | Últimas N mediciones (limit) | OK | [15_ultimas_n_mediciones.md](15_ultimas_n_mediciones.md) |
| 16 | Filtro por magnitud | OK | [16_filtro_por_magnitud.md](16_filtro_por_magnitud.md) |
| 17 | Claves foráneas | OK | [17_claves_foraneas.md](17_claves_foraneas.md) |
| 18 | Separación de responsabilidades | OK | [18_separacion_de_responsabilidades.md](18_separacion_de_responsabilidades.md) |
| extra | Validaciones adicionales (rango, todo o nada, sensor ajeno, timestamp futuro) | OK | [extra_validaciones_adicionales.md](extra_validaciones_adicionales.md) |

Cada archivo indica: datos de entrada, resultado obtenido, código HTTP, registro almacenado o rechazado,
archivo y función donde se implementa la lógica, y una breve explicación.
