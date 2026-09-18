import re

from app.db import get_db
from app.services.productos import format_gramos, format_tipo_venta, presentar_calidad


def _calidad_db(app, producto_id: int) -> str:
    with app.app_context():
        return get_db().execute(
            "SELECT calidad_dato FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()[0]


def test_ok_se_muestra_como_correcto(client, app):
    html = client.get("/productos/2").get_data(as_text=True)
    assert "Correcto" in html
    assert "Los datos de referencia no presentan alertas detectadas." in html
    assert _calidad_db(app, 2) == "OK"


def test_sin_match_mayorista_se_muestra_amigable(client, app):
    html = client.get("/productos/1").get_data(as_text=True)
    assert "Sin referencia mayorista" in html
    assert "No se encontró una coincidencia mayorista exacta para este producto." in html
    assert "SIN_MATCH_MAYORISTA" not in html
    assert _calidad_db(app, 1) == "SIN_MATCH_MAYORISTA"


def test_mayorista_mayor_o_igual_se_muestra_amigable(client, app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo, calidad_dato
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1, ?)
            """,
            ("7799990000001", "PROD MAYORISTA CARO", "MAYORISTA_>=_MINORISTA"),
        )
        db.commit()
        producto_id = db.execute(
            "SELECT producto_id FROM productos WHERE codigo_ean = ?",
            ("7799990000001",),
        ).fetchone()[0]

    html = client.get(f"/productos/{producto_id}").get_data(as_text=True)
    assert "Revisar precio mayorista" in html
    assert "MAYORISTA_>=_MINORISTA" not in html
    assert _calidad_db(app, producto_id) == "MAYORISTA_>=_MINORISTA"


def test_manual_se_muestra_amigable(client, app):
    client.post(
        "/productos/nuevo",
        data={
            "descripcion": "PROD MANUAL UI",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "10",
        },
        follow_redirects=True,
    )
    with app.app_context():
        fila = get_db().execute(
            "SELECT producto_id, calidad_dato FROM productos WHERE descripcion = ?",
            ("PROD MANUAL UI",),
        ).fetchone()
    html = client.get(f"/productos/{fila['producto_id']}").get_data(as_text=True)
    assert "Producto manual" in html
    assert "Este producto fue agregado manualmente al catálogo." in html
    assert fila["calidad_dato"] == "MANUAL"


def test_valores_internos_sqlite_no_cambian(client, app):
    html = client.get("/productos/5").get_data(as_text=True)
    assert "Revisar precio de venta" in html
    assert "REVISAR_PRECIO_VENTA_BAJO|SIN_MATCH_MAYORISTA" not in html
    assert _calidad_db(app, 5) == "REVISAR_PRECIO_VENTA_BAJO|SIN_MATCH_MAYORISTA"
    with app.app_context():
        fila = get_db().execute(
            "SELECT tipo_venta, calidad_dato FROM productos WHERE producto_id = 2"
        ).fetchone()
    assert fila["tipo_venta"] == "UNIDAD"
    assert fila["calidad_dato"] == "OK"
    client.get("/productos/2")
    with app.app_context():
        despues = get_db().execute(
            "SELECT tipo_venta, calidad_dato FROM productos WHERE producto_id = 2"
        ).fetchone()
    assert despues["tipo_venta"] == "UNIDAD"
    assert despues["calidad_dato"] == "OK"


def test_unidad_se_presenta_como_por_unidad(client):
    html = client.get("/productos/2").get_data(as_text=True)
    assert "Por unidad" in html
    assert "5 unidades" in html
    assert "10 unidades" in html
    listado = client.get("/productos?q=COCA").get_data(as_text=True)
    assert "Por unidad" in listado


def test_peso_se_presenta_como_por_peso(client):
    html = client.get("/productos/3").get_data(as_text=True)
    assert "Por peso" in html
    assert format_tipo_venta("PESO") == "Por peso"


def test_peso_sigue_mostrando_precio_por_kg(client):
    html = client.get("/productos/3").get_data(as_text=True)
    assert "$16.690 / kg" in html
    assert "$12.000 / kg" in html
    assert "$16.500 / kg" in html
    assert re.search(r"\$16\.690(?! / kg)", html) is None
    listado = client.get("/productos?tipo=PESO").get_data(as_text=True)
    assert "/ kg" in listado


def test_stock_null_se_presenta_sin_stock_inicial(client):
    html = client.get("/productos/3").get_data(as_text=True)
    assert "Sin stock inicial" in html
    assert "El stock se administra desde Inventario." in html


def test_stock_minimo_peso_se_formatea_en_g_kg(client, app):
    assert format_gramos(500) == "500 g"
    assert format_gramos(1500) == "1,5 kg"
    assert format_gramos(2000) == "2 kg"

    html = client.get("/productos/5").get_data(as_text=True)
    assert "500 g" in html
    assert "100 g" in html

    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, stock_minimo, activo
            ) VALUES (?, ?, 'PESO', 'G', 100, 1500, 1)
            """,
            ("2409990000001", "FIAMBRE FORMATO"),
        )
        db.commit()
        producto_id = db.execute(
            "SELECT producto_id FROM productos WHERE codigo_ean = ?",
            ("2409990000001",),
        ).fetchone()[0]
    html = client.get(f"/productos/{producto_id}").get_data(as_text=True)
    assert "1,5 kg" in html


def test_mensajes_flash_principales(client, app):
    alta = client.post(
        "/productos/nuevo",
        data={
            "descripcion": "FLASH ALTA",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "10",
        },
        follow_redirects=True,
    )
    assert "Producto agregado correctamente." in alta.get_data(as_text=True)

    with app.app_context():
        producto_id = get_db().execute(
            "SELECT producto_id FROM productos WHERE descripcion = ?",
            ("FLASH ALTA",),
        ).fetchone()[0]

    edicion = client.post(
        f"/productos/{producto_id}/editar",
        data={
            "descripcion": "FLASH ALTA",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "12",
        },
        follow_redirects=True,
    )
    assert "Producto actualizado correctamente." in edicion.get_data(as_text=True)

    baja = client.post(f"/productos/{producto_id}/desactivar", follow_redirects=True)
    assert "Producto desactivado." in baja.get_data(as_text=True)

    alta_logica = client.post(f"/productos/{producto_id}/reactivar", follow_redirects=True)
    assert "Producto reactivado." in alta_logica.get_data(as_text=True)

    duplicado = client.post(
        "/productos/nuevo",
        data={
            "descripcion": "EAN DUP",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "10",
            "codigo_ean": "0000002674407",
        },
    )
    assert "Ya existe un producto con ese código." in duplicado.get_data(as_text=True)

    negativo = client.post(
        "/productos/nuevo",
        data={
            "descripcion": "PRECIO MAL",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "-1",
        },
    )
    assert "El precio no puede ser negativo." in negativo.get_data(as_text=True)


def test_codigo_interno_muestra_aclaracion(client, app):
    client.post(
        "/productos/nuevo",
        data={
            "descripcion": "SIN CODIGO UI",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "10",
        },
    )
    with app.app_context():
        fila = get_db().execute(
            "SELECT producto_id, codigo_ean FROM productos WHERE descripcion = ?",
            ("SIN CODIGO UI",),
        ).fetchone()
    html = client.get(f"/productos/{fila['producto_id']}").get_data(as_text=True)
    assert fila["codigo_ean"] == "9990000000001"
    assert "Código interno generado por Kiosco Control. No corresponde a un EAN comercial." in html


def test_alcance_local_se_muestra_como_local(client, app):
    html = client.get("/productos/2").get_data(as_text=True)
    assert "Local" in html
    assert "LOCAL" not in html
    with app.app_context():
        valor = get_db().execute(
            "SELECT alcance_precio_compra FROM productos WHERE producto_id = 2"
        ).fetchone()[0]
    assert valor == "LOCAL"


def test_alcance_nacional_se_muestra_como_nacional(client, app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO productos (
                codigo_ean, descripcion, tipo_venta, unidad_stock,
                precio_venta_actual, activo, alcance_precio_compra
            ) VALUES (?, ?, 'UNIDAD', 'UNIDAD', 10, 1, ?)
            """,
            ("7798880000002", "PROD ALCANCE PAIS", "NACIONAL"),
        )
        db.commit()
        producto_id = db.execute(
            "SELECT producto_id FROM productos WHERE codigo_ean = ?",
            ("7798880000002",),
        ).fetchone()[0]

    html = client.get(f"/productos/{producto_id}").get_data(as_text=True)
    assert "Nacional" in html
    assert "NACIONAL" not in html
    with app.app_context():
        valor = get_db().execute(
            "SELECT alcance_precio_compra FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()[0]
    assert valor == "NACIONAL"


def test_presentar_calidad_desconocida_es_razonable():
    resultado = presentar_calidad("NUEVO_CODIGO_RARO")
    assert resultado["etiqueta"] != "NUEVO_CODIGO_RARO"
    assert "NUEVO" in resultado["etiqueta"] or "codigo" in resultado["etiqueta"].lower()
