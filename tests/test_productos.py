import re


def test_productos_responde_200(client):
    response = client.get("/productos")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Productos" in html
    assert "AGUA MINERAL" in html


def test_listado_inicial_solo_activos(client):
    html = client.get("/productos").get_data(as_text=True)
    assert "GALLETA INACTIVA" not in html
    assert "AGUA MINERAL" in html


def test_paginacion_no_carga_todo_en_una_pagina(client):
    html = client.get("/productos").get_data(as_text=True)
    assert "AGUA MINERAL" in html
    assert "COCA COLA 2.25L" in html
    assert "QUESO CREMOSO" not in html
    assert "Página 1 de 3" in html


def test_pagina_1_y_2_son_distintas(client):
    pagina1 = client.get("/productos").get_data(as_text=True)
    pagina2 = client.get("/productos?page=2").get_data(as_text=True)
    assert pagina1 != pagina2
    assert "AGUA MINERAL" in pagina1
    assert "AGUA MINERAL" not in pagina2
    assert "PAN DE MIGA" in pagina2


def test_paginacion_conserva_filtros(client):
    html = client.get("/productos?tipo=UNIDAD&estado=todos&page=2").get_data(as_text=True)
    assert "tipo=UNIDAD" in html
    assert "estado=todos" in html
    assert "page=1" in html


def test_busqueda_por_descripcion(client):
    html = client.get("/productos?q=COCA").get_data(as_text=True)
    assert "COCA COLA 2.25L" in html
    assert "AGUA MINERAL" not in html


def test_busqueda_por_marca(client):
    html = client.get("/productos?q=PRIME").get_data(as_text=True)
    assert "PRESERVATIVOS" in html
    assert "COCA COLA 2.25L" not in html


def test_busqueda_por_ean_exacto(client):
    html = client.get("/productos?q=0000002674407").get_data(as_text=True)
    assert "PRESERVATIVOS" in html
    assert "COCA COLA 2.25L" not in html


def test_busqueda_exacta_8_digitos(client, app):
    from app.db import get_db

    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1)
            """,
            ("00123456", "LAPICERA OCHO"),
        )
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1)
            """,
            ("1001234560001", "CONTIENE SUBCADENA OCHO"),
        )
        db.commit()

    html = client.get("/productos?q=00123456").get_data(as_text=True)
    assert "00123456" in html
    assert "LAPICERA OCHO" in html
    assert "CONTIENE SUBCADENA OCHO" not in html


def test_busqueda_exacta_12_digitos(client, app):
    from app.db import get_db

    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1)
            """,
            ("012345678901", "CUADERNO DOCE"),
        )
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1)
            """,
            ("0123456789010", "CONTIENE SUBCADENA DOCE"),
        )
        db.commit()

    html = client.get("/productos?q=012345678901").get_data(as_text=True)
    assert "012345678901" in html
    assert "CUADERNO DOCE" in html
    assert "CONTIENE SUBCADENA DOCE" not in html


def test_ean_con_cero_inicial_se_conserva(client):
    html = client.get("/productos?q=0000002674407").get_data(as_text=True)
    assert "0000002674407" in html
    assert re.search(r"(?<!\d)2674407(?!\d)", html) is None


def test_filtro_unidad(client):
    html = client.get("/productos?tipo=UNIDAD&estado=todos").get_data(as_text=True)
    assert "COCA COLA 2.25L" in html or "AGUA MINERAL" in html
    assert "QUESO CREMOSO" not in html
    assert "PAN DE MIGA" not in html


def test_filtro_peso(client):
    html = client.get("/productos?tipo=PESO").get_data(as_text=True)
    assert "QUESO CREMOSO" in html
    assert "PAN DE MIGA" in html
    assert "COCA COLA 2.25L" not in html


def test_filtro_activos(client):
    html = client.get("/productos?estado=activos").get_data(as_text=True)
    assert "GALLETA INACTIVA" not in html
    assert "AGUA MINERAL" in html


def test_filtro_inactivos(client):
    html = client.get("/productos?estado=inactivos").get_data(as_text=True)
    assert "GALLETA INACTIVA" in html
    assert "AGUA MINERAL" not in html


def test_busqueda_mas_filtro(client):
    html = client.get("/productos?q=COCA&tipo=UNIDAD").get_data(as_text=True)
    assert "COCA COLA 2.25L" in html
    vacio = client.get("/productos?q=COCA&tipo=PESO").get_data(as_text=True)
    assert "COCA COLA 2.25L" not in vacio
    assert "No hay productos para mostrar." in vacio


def test_detalle_existente_200(client):
    response = client.get("/productos/3")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "QUESO CREMOSO" in html
    assert "2403866000005" in html
    assert "Referencia SEPA" in html


def test_detalle_inexistente_404(client):
    assert client.get("/productos/9999").status_code == 404


def test_detalle_peso_muestra_precio_por_kg(client):
    html = client.get("/productos/3").get_data(as_text=True)
    assert "Por peso" in html
    assert "/ kg" in html
    assert "$16.690 / kg" in html


def test_stock_null_se_muestra_sin_stock_inicial(client):
    html = client.get("/productos/3").get_data(as_text=True)
    assert "Sin stock inicial" in html
