import re
from html import unescape
from urllib.parse import quote, unquote

from app.navegacion import destino_o_fallback, normalizar_destino

LISTA_INVENTARIO = (
    "/inventario?q=COCA&tipo=UNIDAD&estado=con_stock&activo=activos&page=1"
)
LISTA_PRODUCTOS = "/productos?q=coca&tipo=UNIDAD&estado=activos&page=1"
LISTA_PESO = "/inventario?estado=sin_inicial&tipo=PESO&activo=activos&page=2"


def test_next_interno_valido():
    assert normalizar_destino(LISTA_PESO) == LISTA_PESO
    assert destino_o_fallback(LISTA_PESO, "/inventario/") == LISTA_PESO
    assert normalizar_destino("/productos/2/editar") == "/productos/2/editar"
    assert normalizar_destino("/") == "/"


def test_next_url_externa_rechazada():
    assert destino_o_fallback("https://sitio-externo.com", "/inventario/") == "/inventario/"
    assert (
        destino_o_fallback("http://sitio-externo.com/inventario", "/productos/")
        == "/productos/"
    )
    assert normalizar_destino("https://sitio-externo.com") is None


def test_next_protocolo_relativo_rechazado():
    assert destino_o_fallback("//sitio-externo.com", "/inventario/") == "/inventario/"
    assert (
        destino_o_fallback("//sitio-externo.com/inventario", "/productos/")
        == "/productos/"
    )
    assert normalizar_destino("/%2F%2Fsitio-externo.com") is None
    assert normalizar_destino("/\\sitio-externo.com") is None


def test_next_ausente_usa_fallback():
    assert destino_o_fallback(None, "/inventario/") == "/inventario/"
    assert destino_o_fallback("", "/productos/") == "/productos/"
    assert destino_o_fallback("   ", "/inventario/") == "/inventario/"


def test_filtros_inventario_viajan_en_los_enlaces(client):
    html = client.get(LISTA_INVENTARIO).get_data(as_text=True)
    assert "history.back" not in html
    assert "/productos/2" in html
    assert "Gestionar" in html
    assert "/inventario/2/reposicion" not in html
    assert "/inventario/2/ajuste" not in html
    assert "/inventario/2/descuento" not in html
    assert "/inventario/2/movimientos" not in html
    for pieza in ("q%3DCOCA", "tipo%3DUNIDAD", "estado%3Dcon_stock", "activo%3Dactivos", "page%3D1"):
        assert pieza in html


def test_el_enlace_generado_regresa_al_mismo_listado(client):
    html = client.get(LISTA_INVENTARIO).get_data(as_text=True)
    hrefs = [unescape(href) for href in re.findall(r'href="([^"]+)"', html)]
    detalle = next(href for href in hrefs if href.startswith("/productos/2"))
    pagina = client.get(detalle).get_data(as_text=True)
    assert "← Volver a resultados" in pagina
    assert 'href="/inventario?q=COCA&amp;tipo=UNIDAD&amp;estado=con_stock&amp;activo=activos&amp;page=1"' in pagina
    assert "history.back" not in pagina


def test_pagina_de_inventario_se_conserva_en_el_enlace(client):
    html = client.get(
        "/inventario?tipo=UNIDAD&estado=todos&activo=activos&page=2"
    ).get_data(as_text=True)
    assert "PRESERVATIVOS" in html
    assert "page%3D2" in html
    assert "tipo%3DUNIDAD" in html
    assert "estado%3Dtodos" in html
    assert "activo%3Dactivos" in html


def test_volver_desde_producto_movimientos_y_operaciones(client):
    origen = client.get(LISTA_INVENTARIO).get_data(as_text=True)
    assert "next=" in origen
    paginas = (
        f"/productos/2?next={quote(LISTA_INVENTARIO, safe='')}",
        f"/inventario/2/movimientos?next={quote(LISTA_INVENTARIO, safe='')}",
        f"/inventario/2/reposicion?next={quote(LISTA_INVENTARIO, safe='')}",
        f"/inventario/2/ajuste?next={quote(LISTA_INVENTARIO, safe='')}",
        f"/inventario/2/descuento?next={quote(LISTA_INVENTARIO, safe='')}",
    )
    for ruta in paginas:
        html = client.get(ruta).get_data(as_text=True)
        assert "← Volver a resultados" in html
        assert "history.back" not in html
        assert "q=COCA" in html
        assert "tipo=UNIDAD" in html
        assert "estado=con_stock" in html
        assert "activo=activos" in html
        assert "page=1" in html
        assert "Ver producto" in html or ruta.startswith("/productos/")


def test_contexto_inventario_sobrevive_al_post(client):
    respuesta = client.post(
        "/inventario/2/reposicion",
        data={"cantidad": "4", "next": LISTA_INVENTARIO},
        follow_redirects=False,
    )
    destino = unquote(respuesta.location)
    assert destino.startswith("/inventario/2/movimientos")
    assert LISTA_INVENTARIO in destino
    html = client.get(respuesta.location).get_data(as_text=True)
    assert "← Volver a resultados" in html
    assert "q=COCA" in html
    assert "tipo=UNIDAD" in html
    assert "estado=con_stock" in html
    assert "activo=activos" in html
    assert "page=1" in html
    assert "history.back" not in html


def test_busqueda_tipo_estado_activo_y_pagina_en_el_retorno(client):
    html = client.get(
        "/inventario/2/ajuste",
        query_string={"next": LISTA_PESO},
    ).get_data(as_text=True)
    assert "← Volver a resultados" in html
    assert "estado=sin_inicial" in html
    assert "tipo=PESO" in html
    assert "activo=activos" in html
    assert "page=2" in html


def test_filtros_de_productos_viajan_al_detalle(client):
    html = client.get(
        "/productos?q=coca&tipo=UNIDAD&estado=activos&page=1"
    ).get_data(as_text=True)
    assert "COCA COLA 2.25L" in html
    for pieza in ("q%3Dcoca", "tipo%3DUNIDAD", "estado%3Dactivos", "page%3D1"):
        assert pieza in html
    detalle = client.get(
        "/productos/2",
        query_string={"next": LISTA_PRODUCTOS},
    ).get_data(as_text=True)
    assert "← Volver a resultados" in html or "← Volver a resultados" in detalle
    assert "q=coca" in detalle
    assert "tipo=UNIDAD" in detalle
    assert "estado=activos" in detalle
    assert "page=1" in detalle
    assert "/productos/2/editar?next=" in detalle
    assert "q%3Dcoca" in detalle
    assert "tipo%3DUNIDAD" in detalle
    assert "estado%3Dactivos" in detalle
    assert "page%3D1" in detalle


def test_pagina_de_productos_se_conserva(client):
    html = client.get("/productos?tipo=UNIDAD&estado=activos&page=2").get_data(as_text=True)
    assert "PRESERVATIVOS" in html
    assert "page%3D2" in html
    assert "tipo%3DUNIDAD" in html
    assert "estado%3Dactivos" in html


def test_edicion_conserva_el_contexto(client, app):
    editar = client.get(
        "/productos/2/editar",
        query_string={"next": LISTA_PRODUCTOS},
    )
    html = editar.get_data(as_text=True)
    assert "← Volver a resultados" in html
    assert 'name="next"' in html
    assert "q=coca" in html
    assert "tipo=UNIDAD" in html
    assert "estado=activos" in html
    assert "page=1" in html
    respuesta = client.post(
        "/productos/2/editar",
        data={
            "descripcion": "COCA COLA 2.25L",
            "marca": "COCA",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "2500",
            "next": LISTA_PRODUCTOS,
        },
        follow_redirects=False,
    )
    destino = unquote(respuesta.location)
    assert destino.startswith("/productos/2")
    assert LISTA_PRODUCTOS in destino
    detalle = client.get(respuesta.location).get_data(as_text=True)
    assert "← Volver a resultados" in detalle
    assert "q=coca" in detalle
    assert "page=1" in detalle
    with app.app_context():
        from app.db import get_db

        fila = get_db().execute(
            "SELECT descripcion FROM productos WHERE producto_id = 2"
        ).fetchone()
    assert fila["descripcion"] == "COCA COLA 2.25L"


def test_next_externo_no_se_muestra_ni_redirige(client):
    inventario = client.get(
        "/inventario/2/ajuste",
        query_string={"next": "https://sitio-externo.com"},
    ).get_data(as_text=True)
    assert "sitio-externo.com" not in inventario
    assert "← Volver a resultados" not in inventario
    assert 'href="/inventario/"' in inventario

    protocolo = client.get(
        "/productos/2",
        query_string={"next": "//sitio-externo.com"},
    ).get_data(as_text=True)
    assert "sitio-externo.com" not in protocolo
    assert "Volver al listado" in protocolo
    assert 'href="/productos/"' in protocolo

    respuesta = client.post(
        "/inventario/2/ajuste",
        data={"stock_real": "9", "next": "https://sitio-externo.com"},
        follow_redirects=False,
    )
    assert "sitio-externo.com" not in respuesta.location
    assert respuesta.location.startswith("/inventario/2/movimientos")


def test_sin_next_usa_el_listado_del_modulo(client):
    inventario = client.get("/inventario/2/descuento").get_data(as_text=True)
    assert "← Volver a resultados" not in inventario
    assert "← Volver al inventario" in inventario
    assert 'href="/inventario/"' in inventario
    assert "history.back" not in inventario

    productos = client.get("/productos/2").get_data(as_text=True)
    assert "← Volver a resultados" not in productos
    assert "Volver al listado" in productos
    assert 'href="/productos/"' in productos
