"""Endpoint de estado del servicio (base de datos y consumidor MQTT)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.tiempo import ahora_utc, formatear_local
from app.database.connection import comprobar_conexion

router = APIRouter(tags=["Estado"])


@router.get("/salud", summary="Estado de la API, la base de datos y el consumidor MQTT")
def estado_del_servicio(request: Request):
    try:
        comprobar_conexion()
        base_de_datos = "ok"
    except Exception as exc:  # noqa: BLE001 - el endpoint nunca debe fallar por esto
        base_de_datos = f"error: {exc.__class__.__name__}"

    cliente = getattr(request.app.state, "mqtt", None)
    return {
        "estado": "ok" if base_de_datos == "ok" else "degradado",
        "hora_colombia": formatear_local(ahora_utc()),
        "base_de_datos": base_de_datos,
        "mqtt": cliente.estado() if cliente is not None else "deshabilitado",
    }
