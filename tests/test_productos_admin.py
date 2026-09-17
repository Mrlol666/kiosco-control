from app.db import get_db


def _contar(app) -> int:
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) AS total FROM productos").fetchone()["total"]


def _producto(app, producto_id: int) -> dict:
    with app.app_context():
        fila = get_db().execute(
            "SELECT * FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()
        return dict(fila)


def _manuales(app) -> list[dict]:
    with app.app_context():
        filas = get_db().execute(
            "SELECT * FROM productos WHERE origen_catalogo = 'MANUAL' ORDER BY producto_id"
        ).fetchall()
        return [dict(fila) for fila in filas]


def _datos_alta(**extra):
    datos = {
        "descripcion": "ALFAJOR TEST",
        "marca": "GUAY",
        "categoria": "GOLOSINAS",
        "tipo_venta": "UNIDAD",
        "precio_venta_actual": "500",
        "precio_compra_actual": "300",
        "stock_minimo": "4",
    }
    datos.update(extra)
    return datos


def test_formulario_nuevo_responde_200(client):
    response = client.get("/productos/nuevo")
    assert response.status_code == 200
    assert "Nuevo producto" in response.get_data(as_text=True)


def test_crear_producto_valido(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(), follow_redirects=True)
    assert response.status_code == 200
    assert "Producto agregado correctamente." in response.get_data(as_text=True)
    assert _contar(app) == antes + 1
    creado = _manuales(app)[0]
    assert creado["origen_catalogo"] == "MANUAL"
    assert creado["calidad_dato"] == "MANUAL"
    assert creado["precio_venta_confirmado"] == 1
    assert creado["precio_compra_confirmado"] == 1
    assert creado["categoria"] == "GOLOSINAS"


def test_crear_producto_unidad(client, app):
    client.post("/productos/nuevo", data=_datos_alta(tipo_venta="UNIDAD"))
    creado = _manuales(app)[0]
    assert creado["tipo_venta"] == "UNIDAD"
    assert creado["unidad_stock"] == "UNIDAD"


def test_crear_producto_peso(client, app):
    client.post(
        "/productos/nuevo",
        data=_datos_alta(descripcion="FIAMBRE TEST", tipo_venta="PESO"),
    )
    creado = _manuales(app)[0]
    assert creado["tipo_venta"] == "PESO"
    assert creado["unidad_stock"] == "G"


def test_unidad_stock_derivada_correctamente(client, app):
    client.post("/productos/nuevo", data=_datos_alta(descripcion="UNIDAD TEST", tipo_venta="UNIDAD"))
    client.post(
        "/productos/nuevo",
        data=_datos_alta(descripcion="PESO TEST", tipo_venta="PESO", codigo_ean="12345678"),
    )
    tipos = {fila["descripcion"]: fila["unidad_stock"] for fila in _manuales(app)}
    assert tipos["UNIDAD TEST"] == "UNIDAD"
    assert tipos["PESO TEST"] == "G"


def test_codigo_8_digitos_conserva_ceros(client, app):
    client.post("/productos/nuevo", data=_datos_alta(codigo_ean="00123456"))
    assert _manuales(app)[0]["codigo_ean"] == "00123456"


def test_codigo_12_digitos_conserva_ceros(client, app):
    client.post("/productos/nuevo", data=_datos_alta(codigo_ean="012345678901"))
    assert _manuales(app)[0]["codigo_ean"] == "012345678901"


def test_codigo_13_digitos_conserva_ceros(client, app):
    client.post("/productos/nuevo", data=_datos_alta(codigo_ean="0001112223334"))
    assert _manuales(app)[0]["codigo_ean"] == "0001112223334"


def test_sin_codigo_genera_interno_13_digitos(client, app):
    client.post("/productos/nuevo", data=_datos_alta())
    codigo = _manuales(app)[0]["codigo_ean"]
    assert len(codigo) == 13
    assert codigo == "9990000000001"
    assert codigo.isdigit()


def test_dos_productos_sin_codigo_reciben_codigos_distintos(client, app):
    client.post("/productos/nuevo", data=_datos_alta(descripcion="MANUAL UNO"))
    client.post("/productos/nuevo", data=_datos_alta(descripcion="MANUAL DOS"))
    codigos = [fila["codigo_ean"] for fila in _manuales(app)]
    assert codigos == ["9990000000001", "9990000000002"]


def test_codigo_duplicado_es_rechazado(client, app):
    antes = _contar(app)
    response = client.post(
        "/productos/nuevo",
        data=_datos_alta(codigo_ean="0000002674407"),
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Ya existe un producto con ese código." in html
    assert _contar(app) == antes


def test_descripcion_vacia_rechazada(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(descripcion="   "))
    assert "descripción es obligatoria" in response.get_data(as_text=True).lower()
    assert _contar(app) == antes


def test_tipo_invalido_rechazado(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(tipo_venta="LITRO"))
    assert "por unidad o por peso" in response.get_data(as_text=True)
    assert _contar(app) == antes


def test_precio_venta_negativo_rechazado(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(precio_venta_actual="-10"))
    assert "no puede ser negativo" in response.get_data(as_text=True)
    assert _contar(app) == antes


def test_precio_compra_negativo_rechazado(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(precio_compra_actual="-1"))
    assert "no puede ser negativo" in response.get_data(as_text=True)
    assert _contar(app) == antes


def test_stock_minimo_negativo_rechazado(client, app):
    antes = _contar(app)
    response = client.post("/productos/nuevo", data=_datos_alta(stock_minimo="-5"))
    assert "no puede ser negativo" in response.get_data(as_text=True)
    assert _contar(app) == antes


def test_stock_actual_queda_null_en_producto_nuevo(client, app):
    client.post("/productos/nuevo", data=_datos_alta())
    assert _manuales(app)[0]["stock_actual"] is None


def test_editar_descripcion(client, app):
    response = client.post(
        "/productos/1/editar",
        data={
            "descripcion": "PRESERVATIVOS EDITADOS",
            "marca": "PRIME",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "5830",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "PRESERVATIVOS EDITADOS" in response.get_data(as_text=True)
    assert _producto(app, 1)["descripcion"] == "PRESERVATIVOS EDITADOS"


def test_editar_precios_y_flags_confirmado(client, app):
    client.post(
        "/productos/1/editar",
        data={
            "descripcion": "PRESERVATIVOS",
            "marca": "PRIME",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "6000",
            "precio_compra_actual": "1500",
        },
    )
    fila = _producto(app, 1)
    assert fila["precio_venta_actual"] == 6000
    assert fila["precio_compra_actual"] == 1500
    assert fila["precio_venta_confirmado"] == 1
    assert fila["precio_compra_confirmado"] == 1


def test_vaciar_precio_compra_deja_null_y_confirmado_0(client, app):
    client.post("/productos/nuevo", data=_datos_alta())
    creado = _manuales(app)[0]
    assert creado["precio_compra_actual"] == 300
    assert creado["precio_compra_confirmado"] == 1

    client.post(
        f"/productos/{creado['producto_id']}/editar",
        data={
            "descripcion": "ALFAJOR TEST",
            "marca": "GUAY",
            "categoria": "GOLOSINAS",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "500",
            "precio_compra_actual": "",
            "stock_minimo": "4",
        },
    )
    fila = _producto(app, creado["producto_id"])
    assert fila["precio_compra_actual"] is None
    assert fila["precio_compra_confirmado"] == 0


def test_codigo_ean_no_cambia_durante_edicion(client, app):
    client.post(
        "/productos/1/editar",
        data={
            "descripcion": "PRESERVATIVOS",
            "codigo_ean": "1111111111111",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "5830",
        },
    )
    assert _producto(app, 1)["codigo_ean"] == "0000002674407"


def test_datos_sepa_no_cambian_durante_edicion(client, app):
    antes = _producto(app, 3)
    client.post(
        "/productos/3/editar",
        data={
            "descripcion": "QUESO CREMOSO EDITADO",
            "marca": "SILVI",
            "tipo_venta": "PESO",
            "precio_venta_actual": "16690",
            "precio_compra_actual": "12000",
        },
    )
    despues = _producto(app, 3)
    assert despues["descripcion"] == "QUESO CREMOSO EDITADO"
    assert despues["precio_venta_dia_28"] == antes["precio_venta_dia_28"]
    assert despues["precio_venta_dia_64"] == antes["precio_venta_dia_64"]
    assert despues["precio_compra_referencia"] == antes["precio_compra_referencia"]
    assert despues["mayorista_referencia"] == antes["mayorista_referencia"]
    assert despues["alcance_precio_compra"] == antes["alcance_precio_compra"]
    assert despues["fecha_minorista"] == antes["fecha_minorista"]
    assert despues["fecha_mayorista"] == antes["fecha_mayorista"]


def test_desactivar_no_elimina_la_fila(client, app):
    antes = _contar(app)
    client.post("/productos/6/desactivar", follow_redirects=True)
    assert _contar(app) == antes
    assert _producto(app, 6)["activo"] == 0


def test_desactivado_aparece_en_inactivos(client, app):
    client.post("/productos/6/desactivar")
    html = client.get("/productos?estado=inactivos").get_data(as_text=True)
    assert "AGUA MINERAL" in html
    activos = client.get("/productos?estado=activos").get_data(as_text=True)
    assert "AGUA MINERAL" not in activos


def test_reactivar_funciona(client, app):
    client.post("/productos/6/desactivar")
    client.post("/productos/6/reactivar", follow_redirects=True)
    assert _producto(app, 6)["activo"] == 1
    html = client.get("/productos?estado=activos").get_data(as_text=True)
    assert "AGUA MINERAL" in html


def test_cambio_unidad_peso_sin_historial(client, app):
    client.post(
        "/productos/6/editar",
        data={
            "descripcion": "AGUA MINERAL",
            "marca": "VILLAVICENCIO",
            "tipo_venta": "PESO",
            "precio_venta_actual": "800",
            "precio_compra_actual": "500",
        },
        follow_redirects=True,
    )
    fila = _producto(app, 6)
    assert fila["tipo_venta"] == "PESO"
    assert fila["unidad_stock"] == "G"


def test_cambio_unidad_peso_bloqueado_con_historial(client, app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO movimientos_stock (producto_id, fecha_hora, tipo, cantidad, unidad, motivo)
            VALUES (2, '2026-01-01T10:00:00', 'AJUSTE', 1, 'UNIDAD', 'test')
            """
        )
        db.commit()

    response = client.post(
        "/productos/2/editar",
        data={
            "descripcion": "COCA COLA 2.25L",
            "marca": "COCA",
            "tipo_venta": "PESO",
            "precio_venta_actual": "2500",
            "precio_compra_actual": "1800",
        },
    )
    html = response.get_data(as_text=True)
    assert "No se puede cambiar la forma de venta porque este producto ya tiene movimientos registrados." in html
    fila = _producto(app, 2)
    assert fila["tipo_venta"] == "UNIDAD"
    assert fila["unidad_stock"] == "UNIDAD"
