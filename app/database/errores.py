"""Interpretación de errores de base de datos, independiente del controlador.

``psycopg`` y ``pg8000`` no reportan los errores igual:

* ``psycopg`` lanza subclases específicas (``ForeignKeyViolation``...) y expone ``sqlstate``.
* ``pg8000`` lanza clases genéricas y entrega el error del servidor como un diccionario
  (``{'C': '23503', 'M': 'mensaje', ...}``) en ``args[0]``.

Por eso la aplicación no depende de la *clase* de la excepción sino del código SQLSTATE.
"""

from __future__ import annotations

from sqlalchemy.exc import InterfaceError, OperationalError

# SQLSTATE de violaciones de restricciones -> nombre usado por psycopg (mismo texto con ambos controladores)
_NOMBRES_SQLSTATE = {
    "23502": "NotNullViolation",
    "23503": "ForeignKeyViolation",
    "23505": "UniqueViolation",
    "23514": "CheckViolation",
}
# Clases de SQLSTATE que significan "la base no está disponible":
# 08 conexión, 28 autorización, 53 falta de recursos, 57 intervención del operador.
_CLASES_NO_DISPONIBLE = ("08", "28", "53", "57")


def _original(exc: BaseException) -> BaseException:
    """La excepción del controlador dentro de la de SQLAlchemy (o la misma si no la envuelve)."""
    return getattr(exc, "orig", None) or exc


def _detalle_servidor(original: BaseException) -> dict | None:
    """pg8000: el error del servidor llega como diccionario en ``args[0]``."""
    if original.args and isinstance(original.args[0], dict):
        return original.args[0]
    return None


def codigo_sqlstate(exc: BaseException) -> str | None:
    """Código SQLSTATE del error (por ejemplo ``23503``), o ``None`` si no lo informa el servidor."""
    original = _original(exc)
    detalle = _detalle_servidor(original)
    if detalle is not None:
        return detalle.get("C")
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


def describir_error(exc: BaseException) -> str:
    """Texto corto y legible: ``NombreDelError: primera línea del mensaje``."""
    original = _original(exc)
    detalle = _detalle_servidor(original)
    mensaje = str(detalle.get("M", "")) if detalle is not None else str(original)
    primera_linea = next((linea.strip() for linea in mensaje.splitlines() if linea.strip()), "")
    nombre = _NOMBRES_SQLSTATE.get(codigo_sqlstate(exc) or "", original.__class__.__name__)
    return f"{nombre}: {primera_linea}" if primera_linea else nombre


def es_error_de_conexion(exc: BaseException) -> bool:
    """¿La base de datos no está disponible (red, autenticación, apagada)? La API responde 503."""
    if isinstance(exc, (OperationalError, InterfaceError)) or getattr(exc, "connection_invalidated", False):
        return True
    codigo = codigo_sqlstate(exc) or ""
    return codigo.startswith(_CLASES_NO_DISPONIBLE)


def pista_error_bd(exc: BaseException) -> str | None:
    """Sugerencia de una línea para los errores de conexión más comunes (o ``None``)."""
    codigo = codigo_sqlstate(exc) or ""
    texto = describir_error(exc).lower()
    if codigo == "28P01" or "password authentication failed" in texto:
        return "Usuario o contraseña incorrectos: revisa DB_USER y DB_PASSWORD en .env."
    if codigo == "3D000" or ("database" in texto and "does not exist" in texto):
        return "La base de datos no existe: revisa DB_NAME en .env."
    if "no encryption" in texto or "requires ssl" in texto or "ssl required" in texto:
        return "El servidor exige conexión cifrada: agrega DB_SSLMODE=require en .env."
    if "refuses ssl" in texto or "does not support ssl" in texto:
        return "El servidor no admite SSL: agrega DB_SSLMODE=disable en .env."
    if es_error_de_conexion(exc):
        return (
            "No se pudo llegar al servidor: revisa DB_HOST y DB_PORT, tu conexión a Internet o VPN "
            "y que ningún firewall bloquee el puerto."
        )
    return None
