"""Endpoints HTTP (FastAPI): respuestas, filtros, hora de Colombia y códigos 200/400/404/422."""

from urllib.parse import quote

import pytest

from .conftest import enviar, payload


def sensor_id(client, codigo: str = "GAS-004") -> int:
    return client.get(f"/sensores/por-codigo/{codigo}").json()["id"]


# -- sensores ---------------------------------------------------------------------------------
def test_listar_sensores(client):
    r = client.get("/sensores")
    assert r.status_code == 200
    assert {s["codigo"] for s in r.json()} >= {"TEST-001", "GAS-004", "AIRE-009", "GAS-005"}


def test_listar_sensores_con_filtros(client):
    r = client.get("/sensores", params={"categoria": "GAS", "activo": "true"})
    assert r.status_code == 200
    assert {s["codigo"] for s in r.json()} == {"GAS-004", "GAS-005"}
    assert all(s["categoria"] == "GAS" for s in r.json())


def test_categoria_invalida_es_422(client):
    assert client.get("/sensores", params={"categoria": "PLASMA"}).status_code == 422


def test_sensor_por_id_y_por_codigo(client):
    por_codigo = client.get("/sensores/por-codigo/GAS-004")
    assert por_codigo.status_code == 200
    esperado = por_codigo.json()
    assert esperado["codigo"] == "GAS-004" and esperado["categoria"] == "GAS"
    assert esperado["fecha_registro_local"].endswith("-05:00")

    por_id = client.get(f"/sensores/{esperado['id']}")
    assert por_id.status_code == 200 and por_id.json() == esperado


def test_sensor_inexistente_es_404(client):
    for ruta in ("/sensores/999999", "/sensores/0", "/sensores/-1", "/sensores/por-codigo/NOPE"):
        r = client.get(ruta)
        assert r.status_code == 404, ruta
        assert "detail" in r.json()


@pytest.mark.parametrize("ruta", ["/sensores/abc", "/sensores/1.5", "/sensores/99999999999"])
def test_id_con_formato_invalido_es_422(client, ruta):
    assert client.get(ruta).status_code == 422


# -- sensor-magnitudes ------------------------------------------------------------------------
def test_magnitudes_de_un_sensor(client):
    r = client.get(f"/sensores/{sensor_id(client)}/magnitudes")
    assert r.status_code == 200
    datos = {m["magnitud"]: m for m in r.json()}
    assert set(datos) == {"co2", "co", "ch4"}
    assert datos["co2"]["unidad"] == "ppm"
    assert (datos["co2"]["valor_minimo"], datos["co2"]["valor_maximo"]) == (0.0, 5000.0)


def test_sensor_magnitud_por_id(client):
    primero = client.get(f"/sensores/{sensor_id(client)}/magnitudes").json()[0]
    r = client.get(f"/sensor-magnitudes/{primero['id']}")
    assert r.status_code == 200 and r.json() == primero


def test_sensor_magnitud_inexistente_es_404_y_formato_invalido_es_422(client):
    assert client.get("/sensor-magnitudes/999999").status_code == 404
    assert client.get("/sensor-magnitudes/abc").status_code == 422
    assert client.get("/sensores/999999/magnitudes").status_code == 404


# -- medición por id ----------------------------------------------------------------------------
def test_medicion_por_id_en_hora_de_colombia(client, db):
    enviar(db, payload(timestamp="2026-10-07T16:25:30Z"))
    lista = client.get(f"/sensores/{sensor_id(client)}/mediciones").json()
    r = client.get(f"/mediciones/{lista[0]['id']}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["sensor_codigo"] == "GAS-004"
    assert cuerpo["magnitud"] == "co2" and cuerpo["unidad"] == "ppm" and cuerpo["valor"] == 412.5
    assert cuerpo["timestamp_local"] == "2026-10-07T11:25:30-05:00"  # 16:25:30 UTC
    assert cuerpo["fecha_recepcion_local"].endswith("-05:00")
    assert "timestamp_utc" not in cuerpo


def test_medicion_inexistente_es_404(client):
    assert client.get("/mediciones/987654321").status_code == 404
    assert client.get("/mediciones/0").status_code == 404


@pytest.mark.parametrize("ruta", ["/mediciones/abc", "/mediciones/99999999999999999999"])
def test_medicion_id_invalido_es_422(client, ruta):
    assert client.get(ruta).status_code == 422


# -- histórico ----------------------------------------------------------------------------------
def test_historico_completo_mas_reciente_primero(client, historico):
    r = client.get(f"/sensores/{sensor_id(client)}/mediciones")
    assert r.status_code == 200
    filas = r.json()
    assert len(filas) == historico == 15
    marcas = [f["timestamp_local"] for f in filas]
    assert marcas == sorted(marcas, reverse=True)
    assert marcas[0] == "2026-10-07T11:04:00-05:00"


def test_historico_en_orden_ascendente(client, historico):
    filas = client.get(f"/sensores/{sensor_id(client)}/mediciones", params={"orden": "asc"}).json()
    marcas = [f["timestamp_local"] for f in filas]
    assert marcas == sorted(marcas) and marcas[0] == "2026-10-07T11:00:00-05:00"


def test_limit_devuelve_las_ultimas_n(client, historico):
    sid = sensor_id(client)
    filas = client.get(f"/sensores/{sid}/mediciones", params={"limit": 4}).json()
    assert len(filas) == 4
    assert {f["timestamp_local"] for f in filas} <= {
        "2026-10-07T11:04:00-05:00",
        "2026-10-07T11:03:00-05:00",
    }
    # 'asc' + limit: las últimas N, presentadas de la más antigua a la más reciente
    asc = client.get(f"/sensores/{sid}/mediciones", params={"limit": 4, "orden": "asc"}).json()
    assert [f["id"] for f in asc] == [f["id"] for f in reversed(filas)]


def test_filtro_por_magnitud(client, historico):
    r = client.get(f"/sensores/{sensor_id(client)}/mediciones", params={"magnitud": "co2"})
    assert r.status_code == 200
    filas = r.json()
    assert len(filas) == 5 and {f["magnitud"] for f in filas} == {"co2"}
    assert [f["valor"] for f in filas] == [404.0, 403.0, 402.0, 401.0, 400.0]


def test_filtro_por_rango_con_zona_utc(client, historico):
    r = client.get(
        f"/sensores/{sensor_id(client)}/mediciones",
        params={"desde": "2026-10-07T16:01:00Z", "hasta": "2026-10-07T16:03:00Z", "magnitud": "co"},
    )
    assert r.status_code == 200
    assert sorted(f["valor"] for f in r.json()) == [1.0, 2.0, 3.0]  # límites inclusivos


def test_filtro_por_rango_sin_zona_es_hora_de_colombia(client, historico):
    # 11:01 y 11:02 en Colombia == 16:01 y 16:02 UTC
    r = client.get(
        f"/sensores/{sensor_id(client)}/mediciones",
        params={"desde": "2026-10-07T11:01:00", "hasta": "2026-10-07T11:02:00", "magnitud": "co"},
    )
    assert sorted(f["valor"] for f in r.json()) == [1.0, 2.0]


def test_filtro_solo_fecha_abarca_el_dia_en_hora_de_colombia(client, historico):
    sid = sensor_id(client)
    assert len(client.get(f"/sensores/{sid}/mediciones", params={"desde": "2026-10-07", "hasta": "2026-10-07"}).json()) == 15
    assert client.get(f"/sensores/{sid}/mediciones", params={"desde": "2026-10-08"}).json() == []


def test_zona_con_signo_mas_codificado(client, historico):
    r = client.get(
        f"/sensores/{sensor_id(client)}/mediciones?desde={quote('2026-10-07T21:00:00+05:00')}"
        f"&hasta={quote('2026-10-07T21:01:00+05:00')}&magnitud=co"
    )
    assert r.status_code == 200 and sorted(f["valor"] for f in r.json()) == [0.0, 1.0]


def test_combinacion_de_filtros(client, historico):
    r = client.get(
        f"/sensores/{sensor_id(client)}/mediciones",
        params={"magnitud": "co2", "desde": "2026-10-07T16:01:00Z", "hasta": "2026-10-07T16:04:00Z", "limit": 2},
    )
    assert [f["valor"] for f in r.json()] == [404.0, 403.0]


def test_desde_mayor_que_hasta_es_400(client, historico):
    r = client.get(
        f"/sensores/{sensor_id(client)}/mediciones",
        params={"desde": "2026-10-08T00:00:00Z", "hasta": "2026-10-07T00:00:00Z"},
    )
    assert r.status_code == 400
    assert "desde" in r.json()["detail"]


@pytest.mark.parametrize(
    "parametros",
    [
        {"limit": 0},
        {"limit": -3},
        {"limit": "muchos"},
        {"limit": 10001},
        {"desde": "no-es-fecha"},
        {"hasta": "2026-13-45"},
        {"desde": ""},
        {"orden": "sideways"},
    ],
)
def test_parametros_invalidos_son_422(client, parametros):
    r = client.get(f"/sensores/{sensor_id(client)}/mediciones", params=parametros)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][0] == "query"


def test_sensor_sin_mediciones_devuelve_lista_vacia(client):
    r = client.get(f"/sensores/{sensor_id(client, 'GAS-005')}/mediciones")
    assert r.status_code == 200 and r.json() == []


def test_historico_de_sensor_inexistente_es_404(client):
    assert client.get("/sensores/999999/mediciones").status_code == 404


def test_magnitud_que_el_sensor_no_tiene_es_404(client, historico):
    r = client.get(f"/sensores/{sensor_id(client)}/mediciones", params={"magnitud": "temperature"})
    assert r.status_code == 404


def test_el_historico_no_mezcla_sensores(client, db):
    enviar(db, payload())
    enviar(db, payload(sensor_id="GAS-005", measurements={"o2": {"value": 20.9, "unit": "%"}}), "iot/sensors/GAS-005/data")
    filas = client.get(f"/sensores/{sensor_id(client)}/mediciones").json()
    assert {f["sensor_codigo"] for f in filas} == {"GAS-004"}


# -- última medición -----------------------------------------------------------------------------
def test_ultima_medicion(client, historico):
    r = client.get(f"/sensores/{sensor_id(client)}/ultima-medicion")
    assert r.status_code == 200
    assert r.json()["timestamp_local"] == "2026-10-07T11:04:00-05:00"


def test_ultima_medicion_por_magnitud(client, historico):
    r = client.get(f"/sensores/{sensor_id(client)}/ultima-medicion", params={"magnitud": "co2"})
    assert r.status_code == 200
    assert (r.json()["magnitud"], r.json()["valor"]) == ("co2", 404.0)


def test_ultima_medicion_sin_datos_o_inexistente_es_404(client):
    assert client.get(f"/sensores/{sensor_id(client, 'GAS-005')}/ultima-medicion").status_code == 404
    assert client.get("/sensores/999999/ultima-medicion").status_code == 404
    assert (
        client.get(f"/sensores/{sensor_id(client)}/ultima-medicion", params={"magnitud": "nope"}).status_code
        == 404
    )


# -- estado ---------------------------------------------------------------------------------------
def test_salud(client):
    r = client.get("/salud")
    assert r.status_code == 200
    assert r.json()["base_de_datos"] == "ok" and r.json()["mqtt"] == "deshabilitado"


def test_la_api_no_expone_escrituras(client):
    for metodo in ("post", "put", "patch", "delete"):
        assert getattr(client, metodo)("/mediciones/1").status_code == 405
        assert getattr(client, metodo)("/sensores").status_code == 405
