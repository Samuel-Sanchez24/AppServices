import csv
import json
from pathlib import Path

# Paso 1 — Verificar Python
print("Hola, Aplicaciones y Servicios Web")

BASE_DIR = Path(__file__).resolve().parent
RUTA_CSV = BASE_DIR / "datos" / "estudiantes.csv"
RUTA_JSON = BASE_DIR / "salida" / "estudiantes_resumen.json"


# Paso 2 — Leer el CSV
def leer_estudiantes(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        return [fila for fila in lector]


# Pasos 3 y 4 — Transformar un estudiante
def transformar_estudiante(estudiante: dict) -> dict:
    return {
        "id": estudiante["codigo"],
        "nombre_completo": f"{estudiante['nombre']} {estudiante['apellido']}",
        "semestre": int(estudiante["semestre"]),
        "promedio": float(estudiante["promedio"]),
        "estado": "Activo" if estudiante["activo"].strip().lower() == "true" else "Inactivo",
    }


# Paso 5 — Transformar todos los registros y guardarlos en una lista
def transformar_estudiantes(estudiantes: list[dict]) -> list[dict]:
    return [transformar_estudiante(estudiante) for estudiante in estudiantes]


# Paso 6 — Serializar a JSON
def serializar_estudiantes(ruta: Path, estudiantes: list[dict]) -> None:
    ruta.parent.mkdir(exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(estudiantes, archivo, indent=2, ensure_ascii=False)


# Paso 7 — Deserializar el JSON generado
def deserializar_estudiantes(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


if __name__ == "__main__":
    estudiantes_csv = leer_estudiantes(RUTA_CSV)
    print(f"Registros leídos del CSV: {len(estudiantes_csv)}")

    estudiantes_transformados = transformar_estudiantes(estudiantes_csv)

    # 6. Serializar
    serializar_estudiantes(RUTA_JSON, estudiantes_transformados)
    print(f"Archivo JSON generado: {RUTA_JSON}")

    # 7. Deserializar y mostrar resultado
    estudiantes_recuperados = deserializar_estudiantes(RUTA_JSON)
    print("\nDatos recuperados desde el JSON:")
    print(estudiantes_recuperados[0])
    print(f"Total recuperado: {len(estudiantes_recuperados)}")