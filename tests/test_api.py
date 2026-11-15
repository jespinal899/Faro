"""Pruebas de la API del dashboard (sección 6 de la guía: validación de KPI y seguridad).

La API se conecta con el rol restringido faro_api (como en producción) a bases temporales
cargadas con el pipeline real.
"""

import os
from datetime import timedelta

import psycopg
import pytest
from conftest import RAIZ, sql, uno
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from backend.app import config as modulo_config
from backend.app.main import app
from backend.app.seguridad import hash_password
from etl.orchestration import pipeline
from simulador import ventas

pytestmark = pytest.mark.integracion

PASSWORD = "Contraseña-de-prueba-123"
SECRETO = "s" * 48


@pytest.fixture(scope="module")
def entorno(bases):
    fuente, analitica = bases
    # Un segundo grupo para el producto (para probar la pertenencia ponderada)
    sql(
        fuente,
        "INSERT INTO warehouse.stock_groups (stock_group_id, stock_group_name, last_edited_by) "
        "VALUES (7, 'USB Novelties', 1);"
        "INSERT INTO warehouse.stock_item_stock_groups "
        "(stock_item_stock_group_id, stock_item_id, stock_group_id, last_edited_by) "
        "VALUES (2, 1, 7, 1)",
    )
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"
    ventas.simular(fuente, dias=5, pedidos=3, semilla=11)
    assert pipeline.ejecutar(fuente, analitica, disparador="ci").estado == "exitoso"

    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    for usuario in ("analista", "bloqueable"):
        sql(
            analitica,
            "INSERT INTO app.usuario (usuario, nombre, password_hash) VALUES (%s, %s, %s)",
            (usuario, f"Usuario {usuario}", hash_password(PASSWORD)),
        )

    url_api = make_conninfo(analitica, options="-c role=faro_api")
    anteriores = {k: os.environ.get(k) for k in ("API_DATABASE_URL", "JWT_SECRET", "COOKIE_SEGURA")}
    os.environ.update(API_DATABASE_URL=url_api, JWT_SECRET=SECRETO, COOKIE_SEGURA="false")
    modulo_config.config.cache_clear()
    yield {"analitica": analitica, "api": url_api}
    for k, v in anteriores.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    modulo_config.config.cache_clear()


@pytest.fixture(scope="module")
def cliente(entorno):
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"usuario": "analista", "password": PASSWORD})
        assert r.status_code == 200
        yield c


def _independiente(analitica: str, where: str = "TRUE", params=None) -> dict:
    """KPI calculados directamente sobre las tablas del DW, sin pasar por la API ni sus vistas."""
    fila = sql(
        analitica,
        "SELECT sum(f.venta_neta), sum(f.utilidad), count(DISTINCT f.factura_id), "
        "count(DISTINCT f.cliente_id), sum(f.cantidad) FROM dw.fact_ventas f "
        "JOIN dw.dim_geografia g ON g.geografia_key = f.geografia_key "
        "JOIN dw.dim_producto p ON p.producto_key = f.producto_key "
        f"WHERE {where}",
        params,
    )[0]
    netas, utilidad, facturas, clientes, unidades = fila
    return {
        "ventas_netas": float(netas or 0),
        "utilidad": float(utilidad or 0),
        "facturas": facturas,
        "clientes_activos": clientes,
        "unidades": unidades or 0,
    }


# ------------------------------------------------------------- acceso y sesión


def test_salud_es_publica(entorno):
    with TestClient(app) as c:
        assert c.get("/api/salud").json() == {"api": "ok", "base_de_datos": "ok"}


@pytest.mark.parametrize(
    "ruta",
    ["/api/kpis", "/api/tendencia", "/api/desglose", "/api/facturas", "/api/facturas/1",
     "/api/opciones", "/api/estado", "/api/auth/me"],
)  # fmt: skip
def test_los_datos_exigen_sesion(entorno, ruta):
    with TestClient(app) as c:
        assert c.get(ruta).status_code == 401


def test_sesion_falsificada_es_rechazada(entorno):
    import jwt

    token = jwt.encode({"sub": "intruso", "nombre": "x", "rol": "admin"}, "otro" * 12, "HS256")
    with TestClient(app) as c:
        assert c.get("/api/kpis", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_correcto_abre_sesion_con_cookie_segura(entorno):
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"usuario": "analista", "password": PASSWORD})
        assert r.status_code == 200
        assert r.json() == {"usuario": "analista", "nombre": "Usuario analista", "rol": "analista"}
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        assert "password" not in r.text.lower()
        assert c.get("/api/auth/me").json()["usuario"] == "analista"
        assert c.post("/api/auth/logout").status_code == 204
        assert c.get("/api/auth/me").status_code == 401


def test_usuario_inexistente_y_clave_incorrecta_dan_el_mismo_mensaje(entorno):
    with TestClient(app) as c:
        a = c.post("/api/auth/login", json={"usuario": "no-existe", "password": "x"})
        b = c.post("/api/auth/login", json={"usuario": "analista", "password": "incorrecta"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    sql(entorno["analitica"], "UPDATE app.usuario SET intentos_fallidos = 0")


def test_bloqueo_tras_cinco_intentos_fallidos(entorno):
    with TestClient(app) as c:
        for _ in range(5):
            assert (
                c.post(
                    "/api/auth/login", json={"usuario": "bloqueable", "password": "x"}
                ).status_code
                == 401
            )
        # Ni siquiera la contraseña correcta entra mientras dura el bloqueo
        r = c.post("/api/auth/login", json={"usuario": "bloqueable", "password": PASSWORD})
    assert r.status_code == 423


# ---------------------------------------------------- KPI contra SQL independiente


def test_kpis_sin_filtros_coinciden_con_el_dw(cliente, entorno):
    actual = cliente.get("/api/kpis").json()["actual"]
    esperado = _independiente(entorno["analitica"])
    for k, v in esperado.items():
        assert actual[k] == pytest.approx(v), k
    assert actual["margen_pct"] == pytest.approx(
        round(100 * esperado["utilidad"] / esperado["ventas_netas"], 2)
    )
    assert actual["ticket_promedio"] == pytest.approx(
        round(esperado["ventas_netas"] / esperado["facturas"], 2)
    )


def test_kpis_con_filtros_combinados(cliente, entorno):
    params = {"desde": "2016-01-05", "hasta": "2016-01-08", "territorio": "Territorio",
              "grupo": "USB Novelties", "incluir_simulados": "true"}  # fmt: skip
    actual = cliente.get("/api/kpis", params=params).json()["actual"]
    esperado = _independiente(
        entorno["analitica"],
        "f.fecha_factura BETWEEN '2016-01-05' AND '2016-01-08' "
        "AND g.territorio_venta = 'Territorio' AND p.grupo_principal = 'USB Novelties'",
    )
    assert esperado["facturas"] > 0
    for k, v in esperado.items():
        assert actual[k] == pytest.approx(v), k


def test_excluir_simulados(cliente, entorno):
    actual = cliente.get("/api/kpis", params={"incluir_simulados": "false"}).json()["actual"]
    esperado = _independiente(entorno["analitica"], "NOT f.es_simulado")
    assert actual["ventas_netas"] == pytest.approx(esperado["ventas_netas"])
    assert actual["facturas"] == esperado["facturas"] == 1  # solo la factura histórica


def test_periodo_sin_datos_devuelve_ceros_sin_error(cliente):
    r = cliente.get("/api/kpis", params={"desde": "2030-01-01", "hasta": "2030-01-31"})
    assert r.status_code == 200
    actual = r.json()["actual"]
    assert (actual["ventas_netas"], actual["facturas"], actual["margen_pct"]) == (0, 0, None)
    assert r.json()["comparacion"]["variacion_pct"]["ventas_netas"] is None


def test_desde_posterior_a_hasta_es_un_error_claro(cliente):
    r = cliente.get("/api/kpis", params={"desde": "2016-02-01", "hasta": "2016-01-01"})
    assert r.status_code == 422


# ---------------------------------------------------------- sin duplicar totales


def test_desglose_suma_el_total_con_otros(cliente, entorno):
    total = _independiente(entorno["analitica"])["ventas_netas"]
    r = cliente.get("/api/desglose", params={"dimension": "grupo", "top": 1}).json()
    assert r["total_ventas_netas"] == pytest.approx(total)
    assert sum(f["ventas_netas"] for f in r["filas"]) == pytest.approx(total)


def test_desglose_por_pertenencia_no_duplica(cliente, entorno):
    total = _independiente(entorno["analitica"])["ventas_netas"]
    r = cliente.get("/api/desglose", params={"dimension": "grupo", "pertenencia": "true"}).json()
    assert {f["nombre"] for f in r["filas"]} == {"Grupo", "USB Novelties"}
    # El producto está en 2 grupos: cada uno recibe la mitad y la suma es el total
    assert sum(f["ventas_netas"] for f in r["filas"]) == pytest.approx(total)


def test_tendencia_suma_el_total(cliente, entorno):
    for g in ("mes", "semana", "dia"):
        puntos = cliente.get("/api/tendencia", params={"granularidad": g}).json()
        total = sum(p["ventas_netas"] for p in puntos)
        assert total == pytest.approx(_independiente(entorno["analitica"])["ventas_netas"]), g


# ------------------------------------------------------- detalle y drill-down


def test_facturas_paginadas_y_navegacion_a_la_factura(cliente, entorno):
    r = cliente.get("/api/facturas", params={"tamano": 2, "orden": "fecha_asc"}).json()
    assert r["total"] == _independiente(entorno["analitica"])["facturas"]
    assert len(r["filas"]) == 2
    primera = r["filas"][0]
    assert primera["factura_id"] == 1 and primera["tiene_venta_bajo_costo"] is True

    detalle = cliente.get(f"/api/facturas/{primera['factura_id']}").json()
    assert len(detalle["lineas"]) == primera["lineas"]
    assert detalle["ventas_netas"] == pytest.approx(primera["ventas_netas"])


def test_limites_de_paginacion(cliente):
    assert cliente.get("/api/facturas", params={"tamano": 101}).status_code == 422
    assert cliente.get("/api/facturas/999999").status_code == 404


def test_estado_y_opciones(cliente):
    estado = cliente.get("/api/estado").json()
    assert estado["lineas_simuladas"] > 0 and estado["ultima_carga_exitosa"] is not None
    opciones = cliente.get("/api/opciones").json()
    assert opciones["territorios"] == ["Territorio"]
    assert opciones["vendedores"] == [{"id": 1, "nombre": "Ana Vendedora"}]


# ------------------------------------------------------------------ seguridad


def test_inyeccion_sql_en_filtros_no_tiene_efecto(cliente):
    r = cliente.get("/api/kpis", params={"territorio": "x' OR '1'='1"})
    assert r.status_code == 200 and r.json()["actual"]["facturas"] == 0
    r = cliente.get("/api/desglose", params={"dimension": "grupo; DROP TABLE dw.fact_ventas"})
    assert r.status_code == 422
    # Un parámetro desconocido se ignora: no altera el resultado
    normal = cliente.get("/api/kpis").json()["actual"]
    assert cliente.get("/api/kpis", params={"campo_inventado": "1"}).json()["actual"] == normal


def test_el_rol_de_la_api_no_ve_el_dw_ni_las_claves(entorno):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        sql(entorno["api"], "SELECT count(*) FROM dw.fact_ventas")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        sql(entorno["api"], "UPDATE app.usuario SET rol = 'admin'")
    assert uno(entorno["api"], "SELECT count(*) > 0 FROM api.ventas")


def test_las_respuestas_no_exponen_credenciales(cliente, entorno):
    textos = [cliente.get(r).text for r in ("/api/kpis", "/api/estado", "/api/opciones")]
    textos.append(TestClient(app).get("/api/openapi.json").text)
    secretos = [SECRETO, PASSWORD, "faro_api", "password_hash"]
    for texto in textos:
        for s in secretos:
            assert s not in texto


def test_la_sesion_expira(entorno, monkeypatch):
    from backend.app import seguridad

    with TestClient(app) as c:
        c.post("/api/auth/login", json={"usuario": "analista", "password": PASSWORD})
        token = c.cookies.get(seguridad.COOKIE)
        datos = __import__("jwt").decode(token, SECRETO, algorithms=["HS256"])
        assert datos["exp"] - datos["iat"] == timedelta(minutes=480).total_seconds()
