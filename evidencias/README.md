# Evidencias del Taller 2

Los archivos de esta carpeta **se generan con los scripts**:

1. `python -m scripts.verificar_conexiones`
   → `00_catalogo_sensor.md` (conexión a PostgreSQL y catálogo del sensor asignado) y
   `00_captura_mqtt_inicial.md` (mensajes reales del tópico y estructura del payload).
2. Dejar corriendo `uvicorn app.main:app --host 127.0.0.1 --port 8000` **al menos 20 minutos**
   (el consumidor MQTT almacena las mediciones válidas y escribe `logs/app.log`).
3. `python -m scripts.generar_evidencias --url http://127.0.0.1:8000`
   → `01_` a `18_` (una por cada prueba de la Actividad 6), `extra_validaciones_adicionales.md`,
   `registro_ejecucion.txt` y `resumen.md` (índice con el estado de cada prueba).

Cada archivo indica: datos de entrada, resultado obtenido, código HTTP (si aplica), registro almacenado
o rechazado, archivo y función donde se implementa la lógica, y una breve explicación.
