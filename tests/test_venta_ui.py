import re
from html import unescape

from app import create_app
from app.db import get_db
from tests.db_fixture import crear_base_de_prueba


def _stock(app, producto_id: int):
    with app.app_context():
        return get_db().execute(
            "SELECT stock_actual FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()[0]


def _html(client, ruta="/venta"):
    return client.get(ruta).get_data(as_text=True)


def test_get_venta_muestra_las_dos_areas(client):
    html = _html(client)
    assert "Carrito actual" in html
    assert "Pendientes (0)" in html
    assert "Confirmar venta" not in html
    assert "codigo_ean" not in html
    navegacion = html[html.index('class="site-nav"') : html.index("</nav>")]
    assert navegacion.index("Venta") < navegacion.index("Productos")
    assert navegacion.index("Productos") < navegacion.index("Inventario")


def test_busqueda_por_nombre_sin_codigo_de_barras(client):
    html = _html(client, "/venta?q=coca")
    assert "COCA COLA 2.25L" in html
    assert "Agregar" in html
    assert "Disponible: 10" in html
    assert "7791234567890" not in html
    assert "GALLETA INACTIVA" not in html


def test_filtro_de_categoria(client, app):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE productos SET categoria = ? WHERE producto_id = 2", ("Bebidas",))
        db.execute("UPDATE productos SET categoria = ? WHERE producto_id = 6", ("Bebidas",))
        db.commit()
    html = _html(client, "/venta?categoria=Bebidas")
    assert "COCA COLA 2.25L" in html
    assert "AGUA MINERAL" in html
    assert "QUESO CREMOSO" not in html


def test_resultados_explican_por_que_no_se_agregan(client, app):
    peso = _html(client, "/venta?q=queso")
    assert "Venta por peso disponible en una próxima versión" in peso
    assert "Agregar" not in peso

    sin_inicial = _html(client, "/venta?q=preserv")
    assert "Stock sin inicializar" in sin_inicial
    assert "Agregar" not in sin_inicial

    with app.app_context():
        db = get_db()
        db.execute("UPDATE productos SET stock_actual = 0 WHERE producto_id = 2")
        db.execute("UPDATE productos SET precio_venta_actual = NULL WHERE producto_id = 6")
        db.execute("UPDATE productos SET stock_actual = 4 WHERE producto_id = 6")
        db.commit()
    cero = _html(client, "/venta?q=coca")
    assert "Sin existencias" in cero
    sin_precio = _html(client, "/venta?q=agua")
    assert "Producto sin precio de venta" in sin_precio


def test_agregar_cambiar_quitar_y_precio_desde_la_pantalla(client, app):
    alta = client.post(
        "/venta/lineas",
        data={"producto_id": "2", "cantidad": "1"},
        follow_redirects=True,
    )
    assert "Producto agregado." in alta.get_data(as_text=True)
    assert "COCA COLA 2.25L" in alta.get_data(as_text=True)
    assert "Total" in alta.get_data(as_text=True)

    cambiada = client.post(
        "/venta/lineas/2",
        data={"cantidad": "3"},
        follow_redirects=True,
    )
    assert "Cantidad actualizada." in cambiada.get_data(as_text=True)
    assert 'value="3"' in cambiada.get_data(as_text=True)

    precio = client.post(
        "/venta/precio",
        data={"producto_id": "2", "precio": "2600"},
        follow_redirects=True,
    )
    assert "El precio se actualizó." in precio.get_data(as_text=True)
    assert "$2.600" in precio.get_data(as_text=True)

    quitada = client.post("/venta/lineas/2/quitar", follow_redirects=True)
    assert "Producto quitado." in quitada.get_data(as_text=True)
    assert "Todavía no agregaste productos." in quitada.get_data(as_text=True)
    assert _stock(app, 2) == 10


def test_stock_insuficiente_no_cambia_existencias(client, app):
    respuesta = client.post(
        "/venta/lineas",
        data={"producto_id": "2", "cantidad": "11"},
        follow_redirects=True,
    )
    assert "No hay suficiente stock." in respuesta.get_data(as_text=True)
    assert _stock(app, 2) == 10


def _accion(html: str, fragmento: str) -> str:
    coincidencia = re.search(rf'action="([^"]*{fragmento}[^"]*)"', html)
    assert coincidencia, fragmento
    return unescape(coincidencia.group(1))


def test_pendiente_retomar_descartar_y_cancelar(client, app):
    client.post("/venta/lineas", data={"producto_id": "2", "cantidad": "2"})
    pendiente = client.post(
        "/venta/pendiente",
        data={"etiqueta": "Juan"},
        follow_redirects=True,
    )
    assert "Venta guardada como pendiente." in pendiente.get_data(as_text=True)
    assert "Todavía no agregaste productos." in pendiente.get_data(as_text=True)

    lista = client.get("/venta?vista=pendientes").get_data(as_text=True)
    assert "Juan" in lista
    assert "COCA COLA 2.25L" in lista
    assert "Pendientes (1)" in lista
    retomada = client.post(_accion(lista, "retomar"), follow_redirects=True)
    assert "Venta retomada." in retomada.get_data(as_text=True)
    assert "COCA COLA 2.25L" in retomada.get_data(as_text=True)

    client.post("/venta/pendiente", data={"etiqueta": "Marta"})
    client.post("/venta/lineas", data={"producto_id": "2", "cantidad": "1"})
    ocupada = client.get("/venta?vista=pendientes").get_data(as_text=True)
    aviso = client.get(unescape(re.search(r'href="([^"]*confirmar=retomar[^"]*)"', ocupada).group(1)))
    assert "Ya hay una venta en curso." in aviso.get_data(as_text=True)
    assert "Dejarla pendiente y abrir esta" in aviso.get_data(as_text=True)
    confirmada = client.post(
        _accion(aviso.get_data(as_text=True), "retomar"),
        data={"confirmar": "1"},
        follow_redirects=True,
    )
    assert "Venta retomada." in confirmada.get_data(as_text=True)

    pendientes = client.get("/venta?vista=pendientes").get_data(as_text=True)
    descarte = client.get(
        unescape(re.search(r'href="([^"]*confirmar=descartar[^"]*)"', pendientes).group(1))
    )
    assert "¿Descartar este pendiente?" in descarte.get_data(as_text=True)
    client.post(
        _accion(descarte.get_data(as_text=True), "descartar"),
        data={"confirmar": "1"},
        follow_redirects=True,
    )
    assert "No hay ventas pendientes." in client.get("/venta?vista=pendientes").get_data(as_text=True)

    cancelar = client.get("/venta?confirmar=cancelar")
    assert "¿Cancelar esta venta?" in cancelar.get_data(as_text=True)
    assert "El stock no se modificará." in cancelar.get_data(as_text=True)
    hecho = client.post("/venta/cancelar", data={"confirmar": "1"}, follow_redirects=True)
    assert "Carrito cancelado." in hecho.get_data(as_text=True)
    assert "Todavía no agregaste productos." in hecho.get_data(as_text=True)
    assert _stock(app, 2) == 10


def test_csrf_de_venta_rechaza_el_alta_sin_token(tmp_path):
    db_path = tmp_path / "csrf-venta.sqlite"
    crear_base_de_prueba(db_path)
    aplicacion = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": True,
            "SECRET_KEY": "test-kiosco-control",
            "DATABASE_PATH": db_path,
            "PAGE_SIZE": 50,
        }
    )
    cliente = aplicacion.test_client()
    respuesta = cliente.post("/venta/lineas", data={"producto_id": "2", "cantidad": "1"})
    assert respuesta.status_code == 400
    with aplicacion.app_context():
        stock = get_db().execute(
            "SELECT stock_actual FROM productos WHERE producto_id = 2"
        ).fetchone()[0]
        lineas = get_db().execute("SELECT COUNT(*) AS total FROM carrito_lineas").fetchone()["total"]
    assert stock == 10
    assert lineas == 0
