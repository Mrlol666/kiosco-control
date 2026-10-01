import inspect
import sqlite3

import pytest

from app import create_app
from app.db import begin_immediate, get_db, rollback_transaccion
from app.services.inventario import InventarioError, cantidad_interna
from tests.db_fixture import crear_base_de_prueba


def _stock(app, producto_id: int):
    with app.app_context():
        return get_db().execute(
            "SELECT stock_actual FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()[0]


def _movimientos(app, producto_id: int) -> list[dict]:
    with app.app_context():
        filas = get_db().execute(
            """
            SELECT *
            FROM movimientos_stock
            WHERE producto_id = ?
            ORDER BY movimiento_id
            """,
            (producto_id,),
        ).fetchall()
        return [dict(fila) for fila in filas]


def _suma(app, producto_id: int):
    with app.app_context():
        return get_db().execute(
            "SELECT SUM(cantidad) AS total FROM movimientos_stock WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()["total"]


def _post_inicial(client, producto_id, cantidad, unidad=None, **extra):
    datos = {"cantidad": cantidad}
    if unidad:
        datos["unidad_entrada"] = unidad
    datos.update(extra)
    return client.post(f"/inventario/{producto_id}/inicial", data=datos, follow_redirects=True)


def _post_reposicion(client, producto_id, cantidad, unidad=None):
    datos = {"cantidad": cantidad}
    if unidad:
        datos["unidad_entrada"] = unidad
    return client.post(
        f"/inventario/{producto_id}/reposicion",
        data=datos,
        follow_redirects=True,
    )


def _post_ajuste(client, producto_id, stock_real, motivo="DIFERENCIA_INVENTARIO", unidad=None):
    datos = {"stock_real": stock_real, "motivo": motivo}
    if unidad:
        datos["unidad_entrada"] = unidad
    return client.post(f"/inventario/{producto_id}/ajuste", data=datos, follow_redirects=True)


def _post_descuento(client, producto_id, cantidad, motivo, unidad=None, **extra):
    datos = {"cantidad": cantidad, "motivo": motivo}
    if unidad:
        datos["unidad_entrada"] = unidad
    datos.update(extra)
    return client.post(
        f"/inventario/{producto_id}/descuento",
        data=datos,
        follow_redirects=True,
    )


def test_cantidad_unidad_acepta_enteros():
    for texto, esperado in (("0", 0), ("1", 1), ("2", 2), ("15", 15), ("100", 100), ("1.0", 1), ("1,0", 1)):
        assert cantidad_interna(texto, "UNIDAD", None, modo="inicial") == esperado


def test_cantidad_unidad_rechaza_decimales():
    for texto in ("1,5", "1.5", "2,25"):
        with pytest.raises(InventarioError, match="entero de unidades"):
            cantidad_interna(texto, "UNIDAD", None, modo="inicial")


def test_cantidad_peso_gramos_kilos_y_decimal():
    assert cantidad_interna("250", "PESO", "G", modo="inicial") == 250
    assert cantidad_interna("1000", "PESO", "G", modo="inicial") == 1000
    assert cantidad_interna("1", "PESO", "KG", modo="inicial") == 1000
    assert cantidad_interna("1,5", "PESO", "KG", modo="inicial") == 1500
    assert cantidad_interna("1.5", "PESO", "KG", modo="inicial") == 1500
    assert cantidad_interna("4,25", "PESO", "KG", modo="inicial") == 4250
    assert cantidad_interna("0", "PESO", "G", modo="inicial") == 0
    assert cantidad_interna("0", "PESO", "KG", modo="inicial") == 0


def test_cantidad_peso_rechaza_gramos_fraccionarios():
    for texto, unidad in (("250,5", "G"), ("250.5", "G"), ("1,0005", "KG")):
        with pytest.raises(InventarioError, match="entero de gramos"):
            cantidad_interna(texto, "PESO", unidad, modo="inicial")


def test_cantidad_reposicion_cero_o_negativa_rechazada():
    with pytest.raises(InventarioError, match="mayor que cero"):
        cantidad_interna("0", "UNIDAD", None, modo="reposicion")
    with pytest.raises(InventarioError, match="mayor que cero"):
        cantidad_interna("-1", "UNIDAD", None, modo="reposicion")


def test_stock_inicial_unidad(client, app):
    response = _post_inicial(client, 6, "12")
    assert "Stock inicial registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 6) == 12
    assert float(_stock(app, 6)).is_integer()
    movimiento = _movimientos(app, 6)[0]
    assert movimiento["tipo"] == "AJUSTE"
    assert movimiento["motivo"] == "STOCK_INICIAL"
    assert movimiento["cantidad"] == 12
    assert movimiento["unidad"] == "UNIDAD"
    assert movimiento["venta_id"] is None
    assert movimiento["fecha_hora"]


def test_stock_inicial_cero_no_queda_null(client, app):
    _post_inicial(client, 6, "0")
    assert _stock(app, 6) == 0
    assert _stock(app, 6) is not None
    html = client.get("/productos/6").get_data(as_text=True)
    assert "Registrar stock inicial" not in html
    assert "0 unidades" in html


def test_stock_inicial_peso_gramos_y_kg(client, app):
    response = _post_inicial(client, 3, "1,5", "KG")
    assert "Stock inicial registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 3) == 1500
    assert float(_stock(app, 3)).is_integer()
    movimiento = _movimientos(app, 3)[0]
    assert movimiento["cantidad"] == 1500
    assert movimiento["unidad"] == "G"
    assert movimiento["motivo"] == "STOCK_INICIAL"

    _post_inicial(client, 5, "250", "G")
    assert "ya tiene stock inicial" in client.post(
        "/inventario/5/inicial",
        data={"cantidad": "1", "unidad_entrada": "G"},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert _stock(app, 5) == 100


def test_segundo_inicial_rechazado(client, app):
    response = _post_inicial(client, 2, "4")
    assert "ya tiene stock inicial" in response.get_data(as_text=True).lower() or "Este producto ya tiene stock inicial." in response.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_inicial_inactivo_rechazado(client, app):
    response = _post_inicial(client, 4, "3")
    assert "Reactivá el producto antes de registrar el stock inicial." in response.get_data(as_text=True)
    assert _stock(app, 4) is None
    assert _movimientos(app, 4) == []


def test_reposicion_suma_unidad(client, app):
    response = _post_reposicion(client, 2, "10")
    assert "Reposición registrada correctamente." in response.get_data(as_text=True)
    assert _stock(app, 2) == 20
    movimiento = _movimientos(app, 2)[0]
    assert movimiento["tipo"] == "ENTRADA"
    assert movimiento["motivo"] == "REPOSICION"
    assert movimiento["cantidad"] == 10
    assert movimiento["unidad"] == "UNIDAD"
    assert movimiento["venta_id"] is None


def test_reposicion_peso_gramos_y_kg(client, app):
    _post_inicial(client, 3, "500", "G")
    response = _post_reposicion(client, 3, "1.5", "KG")
    assert "Reposición registrada correctamente." in response.get_data(as_text=True)
    assert _stock(app, 3) == 2000
    cantidades = [fila["cantidad"] for fila in _movimientos(app, 3)]
    assert cantidades == [500, 1500]


def test_reposicion_sin_inicial_rechazada(client, app):
    response = _post_reposicion(client, 6, "2")
    assert "Primero registrá el stock inicial." in response.get_data(as_text=True)
    assert _stock(app, 6) is None


def test_reposicion_cero_y_negativa_rechazadas(client, app):
    assert "mayor que cero" in _post_reposicion(client, 2, "0").get_data(as_text=True)
    assert "mayor que cero" in _post_reposicion(client, 2, "-3").get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_reposicion_inactivo_rechazada(client, app):
    client.post("/productos/2/desactivar")
    response = _post_reposicion(client, 2, "4")
    assert "Reactivá el producto antes de registrar una reposición." in response.get_data(as_text=True)
    assert _stock(app, 2) == 10


def test_ajuste_baja_sube_y_a_cero(client, app):
    baja = _post_ajuste(client, 2, "17", "DIFERENCIA_INVENTARIO")
    assert "Stock ajustado correctamente." in baja.get_data(as_text=True)
    assert _stock(app, 2) == 17
    assert _movimientos(app, 2)[0]["cantidad"] == 7
    assert _movimientos(app, 2)[0]["tipo"] == "AJUSTE"

    assert _movimientos(app, 2)[0]["motivo"] == "DIFERENCIA_INVENTARIO"

    client.post(
        "/inventario/2/ajuste",
        data={"stock_real": "14", "motivo": "ROTURA"},
    )
    assert _stock(app, 2) == 14
    assert _movimientos(app, 2)[1]["cantidad"] == -3
    assert _movimientos(app, 2)[1]["motivo"] == "DIFERENCIA_INVENTARIO"

    _post_ajuste(client, 2, "0", "MERMA")
    assert _stock(app, 2) == 0
    assert _movimientos(app, 2)[2]["cantidad"] == -14
    assert _movimientos(app, 2)[2]["motivo"] == "DIFERENCIA_INVENTARIO"


def test_ajuste_diferencia_cero_rechazada(client, app):
    response = _post_ajuste(client, 2, "10")
    assert (
        "El stock real coincide con el stock registrado. No es necesario realizar un ajuste."
        in response.get_data(as_text=True)
    )
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_ajuste_negativo_y_motivo_invalido(client, app):
    negativo = _post_ajuste(client, 2, "-1")
    assert "El stock real no puede ser negativo." in negativo.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []

    formulario = client.get("/inventario/2/ajuste").get_data(as_text=True)
    assert "Stock real contado" in formulario
    assert "Rotura" not in formulario
    assert "Vencimiento" not in formulario
    assert "Merma" not in formulario
    assert "Consumo interno" not in formulario
    assert 'name="motivo"' not in formulario

    aplicado = _post_ajuste(client, 2, "8", "ROBO")
    assert "Stock ajustado correctamente." in aplicado.get_data(as_text=True)
    assert _stock(app, 2) == 8
    assert _movimientos(app, 2)[0]["motivo"] == "DIFERENCIA_INVENTARIO"
    assert _movimientos(app, 2)[0]["cantidad"] == -2


def test_ajuste_peso_guarda_diferencia_en_gramos(client, app):
    _post_inicial(client, 3, "2", "KG")
    response = _post_ajuste(client, 3, "1,5", "MERMA", unidad="KG")
    assert "Stock ajustado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 3) == 1500
    assert _movimientos(app, 3)[1]["cantidad"] == -500
    assert _movimientos(app, 3)[1]["unidad"] == "G"
    assert _movimientos(app, 3)[1]["motivo"] == "DIFERENCIA_INVENTARIO"


def test_ajuste_permitido_en_inactivo(client, app):
    client.post("/productos/2/desactivar")
    response = _post_ajuste(client, 2, "7", "VENCIMIENTO")
    assert "Stock ajustado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 2) == 7
    fila = _movimientos(app, 2)[0]
    assert fila["cantidad"] == -3
    assert fila["motivo"] == "DIFERENCIA_INVENTARIO"
    with app.app_context():
        activo = get_db().execute(
            "SELECT activo FROM productos WHERE producto_id = 2"
        ).fetchone()[0]
    assert activo == 0


def test_ajuste_sin_inicial_rechazado(client, app):
    response = _post_ajuste(client, 6, "1", "OTRO")
    assert "Primero registrá el stock inicial." in response.get_data(as_text=True)
    assert _movimientos(app, 6) == []


def test_unidad_no_multiplica_si_envian_kg(client, app):
    _post_inicial(client, 6, "2", "KG")
    assert _stock(app, 6) == 2


def test_historial_amigable_y_ordenado(client, app, monkeypatch):
    marcas = iter(["2026-10-01 10:00:00", "2026-10-01 11:00:00", "2026-10-01 12:00:00"])
    monkeypatch.setattr("app.services.inventario.ahora_local", lambda: next(marcas))
    _post_inicial(client, 6, "20")
    _post_reposicion(client, 6, "10")
    _post_ajuste(client, 6, "38", "DIFERENCIA_INVENTARIO")

    html = client.get("/inventario/6/movimientos").get_data(as_text=True)
    assert html.index("Diferencia de inventario") < html.index("Reposición")
    assert "Stock inicial" in client.get("/inventario/6/movimientos?page=2").get_data(as_text=True)
    assert "STOCK_INICIAL" not in html
    assert "REPOSICION" not in html
    assert "DIFERENCIA_INVENTARIO" not in html
    assert "AJUSTE" not in html
    assert "ENTRADA" not in html
    assert "+10 unidades" in html
    assert "+8 unidades" in html
    fechas = [fila["fecha_hora"] for fila in _movimientos(app, 6)]
    assert fechas == ["2026-10-01 10:00:00", "2026-10-01 11:00:00", "2026-10-01 12:00:00"]


def test_historial_peso_muestra_g_y_kg(client):
    _post_inicial(client, 3, "4,5", "KG")
    _post_descuento(client, 3, "250", "MERMA", unidad="G")
    html = client.get("/inventario/3/movimientos").get_data(as_text=True)
    assert "+4,5 kg" in html
    assert "-250 g" in html
    assert "Merma" in html
    assert "Stock inicial" in html


def test_invariante_suma_de_movimientos(client, app):
    _post_inicial(client, 6, "20")
    _post_reposicion(client, 6, "10")
    _post_ajuste(client, 6, "28", "ROTURA")
    assert _suma(app, 6) == 28
    assert _stock(app, 6) == 28


def test_movimientos_no_se_borran_ni_actualizan():
    codigo = inspect.getsource(__import__("app.repositories.inventario", fromlist=["inventario"]))
    assert "DELETE" not in codigo.upper()
    assert "UPDATE movimientos_stock" not in codigo


def test_begin_immediate_se_ejecuta(app):
    vistos = []
    with app.app_context():
        get_db().set_trace_callback(vistos.append)
        begin_immediate()
        rollback_transaccion()
    assert any("BEGIN IMMEDIATE" in linea for linea in vistos)


def test_rollback_si_falla_insert(client, app, monkeypatch):
    orden = []
    repo = __import__("app.services.inventario", fromlist=["inventario_repo"]).inventario_repo
    actualizar = repo.actualizar_stock
    commit = __import__("app.services.inventario", fromlist=["commit_transaccion"]).commit_transaccion
    rollback = __import__("app.services.inventario", fromlist=["rollback_transaccion"]).rollback_transaccion

    def actualizar_vigilado(producto_id, stock):
        orden.append("update")
        return actualizar(producto_id, stock)

    def insertar_falla(**kwargs):
        orden.append("insert")
        raise sqlite3.IntegrityError("forzado")

    def commit_vigilado():
        orden.append("commit")
        return commit()

    def rollback_vigilado():
        orden.append("rollback")
        return rollback()

    monkeypatch.setattr(repo, "actualizar_stock", actualizar_vigilado)
    monkeypatch.setattr(repo, "insertar_movimiento", insertar_falla)
    monkeypatch.setattr("app.services.inventario.commit_transaccion", commit_vigilado)
    monkeypatch.setattr("app.services.inventario.rollback_transaccion", rollback_vigilado)

    response = _post_inicial(client, 6, "9")
    assert "No se pudo guardar el movimiento de stock." in response.get_data(as_text=True)
    assert _stock(app, 6) is None
    assert _movimientos(app, 6) == []
    assert orden == ["update", "insert", "rollback"]


def test_no_hay_movimiento_si_falla_update(client, app, monkeypatch):
    repo = __import__("app.services.inventario", fromlist=["inventario_repo"]).inventario_repo

    def actualizar_falla(producto_id, stock):
        raise sqlite3.OperationalError("forzado")

    def insertar_no( **kwargs):
        raise AssertionError("No debía insertarse un movimiento.")

    monkeypatch.setattr(repo, "actualizar_stock", actualizar_falla)
    monkeypatch.setattr(repo, "insertar_movimiento", insertar_no)
    response = _post_reposicion(client, 2, "3")
    assert "No se pudo guardar el movimiento de stock." in response.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_un_solo_commit(client, app, monkeypatch):
    llamadas = {"commit": 0, "rollback": 0}
    commit = __import__("app.db", fromlist=["commit_transaccion"]).commit_transaccion
    rollback = __import__("app.db", fromlist=["rollback_transaccion"]).rollback_transaccion

    def commit_vigilado():
        llamadas["commit"] += 1
        return commit()

    def rollback_vigilado():
        llamadas["rollback"] += 1
        return rollback()

    monkeypatch.setattr("app.services.inventario.commit_transaccion", commit_vigilado)
    monkeypatch.setattr("app.services.inventario.rollback_transaccion", rollback_vigilado)
    _post_inicial(client, 6, "4")
    assert llamadas == {"commit": 1, "rollback": 0}
    assert _stock(app, 6) == 4


def test_listado_busqueda_filtros_y_paginacion(client):
    html = client.get("/inventario").get_data(as_text=True)
    assert "Inventario" in html
    assert "v0.2" in html
    assert "AGUA MINERAL" in html
    assert "COCA COLA 2.25L" in html
    assert "GALLETA INACTIVA" not in html
    assert "Página 1 de 3" in html
    assert "Sin stock inicial" in html
    assert "Stock disponible" in html

    pagina2 = client.get("/inventario?page=2").get_data(as_text=True)
    assert "PAN DE MIGA" in pagina2
    assert "Stock bajo" in pagina2
    assert "AGUA MINERAL" not in pagina2

    assert "COCA COLA 2.25L" in client.get("/inventario?q=COCA").get_data(as_text=True)
    assert "PRESERVATIVOS" in client.get("/inventario?q=PRIME").get_data(as_text=True)
    assert "PRESERVATIVOS" in client.get("/inventario?q=0000002674407").get_data(as_text=True)
    assert "COCA COLA 2.25L" not in client.get("/inventario?q=0000002674407").get_data(as_text=True)

    sin_inicial = client.get("/inventario?estado=sin_inicial").get_data(as_text=True)
    assert "AGUA MINERAL" in sin_inicial
    assert "COCA COLA 2.25L" not in sin_inicial
    assert "PAN DE MIGA" not in sin_inicial

    con_stock = client.get("/inventario?estado=con_stock").get_data(as_text=True)
    assert "COCA COLA 2.25L" in con_stock
    assert "PAN DE MIGA" in con_stock
    assert "AGUA MINERAL" not in con_stock

    bajo = client.get("/inventario?estado=bajo").get_data(as_text=True)
    assert "PAN DE MIGA" in bajo
    assert "COCA COLA 2.25L" not in bajo

    inactivos = client.get("/inventario?activo=inactivos").get_data(as_text=True)
    assert "GALLETA INACTIVA" in inactivos
    assert "AGUA MINERAL" not in inactivos

    todos = client.get("/inventario?activo=todos").get_data(as_text=True)
    assert "GALLETA INACTIVA" in todos or "AGUA MINERAL" in todos
    assert "Página 1 de 3" in todos


def test_cero_sale_de_sin_inicial_y_entra_en_con_stock(client):
    _post_inicial(client, 6, "0")
    sin_inicial = client.get("/inventario?estado=sin_inicial").get_data(as_text=True)
    con_existencias = client.get("/inventario?estado=con_existencias").get_data(as_text=True)
    sin_existencias = client.get("/inventario?estado=sin_existencias").get_data(as_text=True)
    assert "AGUA MINERAL" not in sin_inicial
    assert "AGUA MINERAL" not in con_existencias
    assert "AGUA MINERAL" in sin_existencias
    assert "Sin existencias" in sin_existencias
    assert "Stock disponible" not in sin_existencias


def test_detalle_muestra_acciones_segun_estado(client):
    activo_null = client.get("/productos/6").get_data(as_text=True)
    assert "Registrar stock inicial" in activo_null
    assert "Ver movimientos" in activo_null
    assert "Reponer stock" not in activo_null
    assert "Descontar stock" not in activo_null

    con_stock = client.get("/productos/2").get_data(as_text=True)
    assert "Reponer stock" in con_stock
    assert "Ajustar stock" in con_stock
    assert "Descontar stock" in con_stock
    assert "Registrar stock inicial" not in con_stock

    inactivo = client.get("/productos/4").get_data(as_text=True)
    assert "Inactivo" in inactivo
    assert "Ver movimientos" in inactivo
    assert "Registrar stock inicial" not in inactivo
    assert "Reponer stock" not in inactivo
    assert "Ajustar stock" not in inactivo
    assert "Descontar stock" not in inactivo


def _metrica(html: str, etiqueta: str) -> str:
    import re

    match = re.search(
        rf'class="metrics-value">([^<]+)</span>\s*<span class="metrics-label">{re.escape(etiqueta)}</span>',
        html,
    )
    assert match, etiqueta
    return match.group(1).strip()


def test_dashboard_sin_stock_solo_activos_y_null_no_es_bajo(client, app):
    html = client.get("/").get_data(as_text=True)
    assert "estado=sin_inicial" in html
    assert "estado=bajo" in html
    assert _metrica(html, "Sin stock inicial") == "3"
    assert _metrica(html, "Con stock bajo") == "1"

    _post_inicial(client, 6, "4")
    despues = client.get("/").get_data(as_text=True)
    assert _metrica(despues, "Sin stock inicial") == "2"
    assert _metrica(despues, "Con stock bajo") == "1"

    client.post(
        "/productos/1/editar",
        data={
            "descripcion": "PRESERVATIVOS",
            "marca": "PRIME",
            "tipo_venta": "UNIDAD",
            "precio_venta_actual": "5830",
            "stock_minimo": "3",
        },
    )
    bajo = client.get("/inventario?estado=bajo").get_data(as_text=True)
    assert "PRESERVATIVOS" not in bajo
    with app.app_context():
        metricas = get_db().execute(
            """
            SELECT
                SUM(CASE WHEN activo = 1 AND stock_actual IS NULL THEN 1 ELSE 0 END) AS sin_stock,
                SUM(
                    CASE
                        WHEN activo = 1
                         AND stock_actual IS NOT NULL
                         AND stock_minimo IS NOT NULL
                         AND stock_actual <= stock_minimo
                        THEN 1 ELSE 0
                    END
                ) AS stock_bajo
            FROM productos
            """
        ).fetchone()
    assert metricas["sin_stock"] == 2
    assert metricas["stock_bajo"] == 1


def test_csrf_rechaza_post_sin_token(tmp_path):
    db_path = tmp_path / "csrf.sqlite"
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
    response = cliente.post("/inventario/6/inicial", data={"cantidad": "4"})
    assert response.status_code == 400
    with aplicacion.app_context():
        stock = get_db().execute(
            "SELECT stock_actual FROM productos WHERE producto_id = 6"
        ).fetchone()[0]
    assert stock is None


def test_busqueda_no_interpreta_curly_como_sql(client):
    html = client.get("/inventario?q=%").get_data(as_text=True)
    assert "0 resultados" in html


def test_filtro_forma_de_venta_todos_unidad_y_peso(client):
    todos = client.get("/inventario?tipo=todos").get_data(as_text=True)
    assert "5 resultados" in todos
    assert "COCA COLA 2.25L" in todos

    unidad = client.get("/inventario?tipo=UNIDAD").get_data(as_text=True)
    assert "3 resultados" in unidad
    assert "COCA COLA 2.25L" in unidad
    assert "QUESO CREMOSO" not in unidad
    assert "PAN DE MIGA" not in unidad

    peso = client.get("/inventario?tipo=PESO").get_data(as_text=True)
    assert "2 resultados" in peso
    assert "QUESO CREMOSO" in peso
    assert "PAN DE MIGA" in peso
    assert "COCA COLA 2.25L" not in peso


def test_filtro_forma_de_venta_combinado(client):
    por_estado = client.get(
        "/inventario?estado=sin_inicial&tipo=PESO&activo=activos"
    ).get_data(as_text=True)
    assert "QUESO CREMOSO" in por_estado
    assert "PAN DE MIGA" not in por_estado
    assert "COCA COLA 2.25L" not in por_estado

    inactivos = client.get("/inventario?tipo=UNIDAD&activo=inactivos").get_data(as_text=True)
    assert "GALLETA INACTIVA" in inactivos
    assert "AGUA MINERAL" not in inactivos

    busqueda = client.get("/inventario?q=COCA&tipo=UNIDAD").get_data(as_text=True)
    assert "COCA COLA 2.25L" in busqueda
    otro_tipo = client.get("/inventario?q=COCA&tipo=PESO").get_data(as_text=True)
    assert "COCA COLA 2.25L" not in otro_tipo
    assert "0 resultados" in otro_tipo


def test_paginacion_conserva_tipo(client):
    html = client.get("/inventario?tipo=UNIDAD&estado=todos&activo=activos").get_data(as_text=True)
    assert "tipo=UNIDAD" in html
    assert "page=2" in html
    assert "estado=todos" in html
    pagina2 = client.get("/inventario?tipo=UNIDAD&estado=todos&activo=activos&page=2").get_data(as_text=True)
    assert "tipo=UNIDAD" in pagina2
    assert "page=1" in pagina2
    assert "PRESERVATIVOS" in pagina2


def test_formularios_tienen_enlaces_explicitos(client):
    paginas = (
        "/inventario/6/inicial",
        "/inventario/2/reposicion",
        "/inventario/2/ajuste",
        "/inventario/2/descuento",
    )
    for ruta in paginas:
        html = client.get(ruta).get_data(as_text=True)
        assert "history.back" not in html
        assert "← Volver al inventario" in html
        assert "Ver producto" in html
        assert "Ver movimientos" in html
        assert 'href="/inventario/"' in html
        assert 'href="/productos/' in html
        assert "Volver a movimientos" not in html

    historial = client.get("/inventario/6/movimientos").get_data(as_text=True)
    assert "history.back" not in historial
    assert "← Volver al inventario" in historial
    assert "Ver producto" in historial
    assert 'href="/productos/6"' in historial


def test_rotura_hacia_cero_es_valida(client, app):
    response = _post_descuento(client, 2, "10", "ROTURA")
    assert "Descuento registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 2) == 0
    movimiento = _movimientos(app, 2)[0]
    assert movimiento["motivo"] == "ROTURA"
    assert movimiento["tipo"] == "AJUSTE"
    assert movimiento["cantidad"] == -10
    assert movimiento["unidad"] == "UNIDAD"


@pytest.mark.parametrize("motivo", ["ROTURA", "VENCIMIENTO", "MERMA", "CONSUMO_INTERNO"])
def test_descuento_registra_salida_por_motivo(client, app, motivo):
    response = _post_descuento(client, 2, "2", motivo)
    assert "Descuento registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 2) == 8
    movimiento = _movimientos(app, 2)[0]
    assert movimiento["motivo"] == motivo
    assert movimiento["tipo"] == "AJUSTE"
    assert movimiento["cantidad"] == -2
    assert movimiento["unidad"] == "UNIDAD"


def test_diferencia_inventario_acepta_subir_y_bajar(client, app):
    alta = _post_ajuste(client, 2, "15", "DIFERENCIA_INVENTARIO")
    assert "Stock ajustado correctamente." in alta.get_data(as_text=True)
    assert _stock(app, 2) == 15
    assert _movimientos(app, 2)[0]["cantidad"] == 5

    baja = _post_ajuste(client, 2, "8", "DIFERENCIA_INVENTARIO")
    assert "Stock ajustado correctamente." in baja.get_data(as_text=True)
    assert _stock(app, 2) == 8
    assert _movimientos(app, 2)[1]["cantidad"] == -7


def test_otro_acepta_subir_y_bajar(client, app):
    alta = _post_ajuste(client, 2, "12", "OTRO")
    assert "Stock ajustado correctamente." in alta.get_data(as_text=True)
    assert _stock(app, 2) == 12
    assert _movimientos(app, 2)[0]["motivo"] == "DIFERENCIA_INVENTARIO"
    assert _movimientos(app, 2)[0]["cantidad"] == 2

    baja = _post_descuento(client, 2, "3", "OTRO")
    assert "Descuento registrado correctamente." in baja.get_data(as_text=True)
    assert _stock(app, 2) == 9
    assert _movimientos(app, 2)[1]["motivo"] == "OTRO"
    assert _movimientos(app, 2)[1]["cantidad"] == -3


def test_ajuste_por_conteo_unidad_baja_y_sube(client, app):
    _post_inicial(client, 6, "20")
    formulario = client.get("/inventario/6/ajuste").get_data(as_text=True)
    assert "Ajustar stock por conteo" in formulario
    assert "Rotura" not in formulario
    assert 'name="motivo"' not in formulario

    igual = _post_ajuste(client, 6, "20")
    assert (
        "El stock real coincide con el stock registrado. No es necesario realizar un ajuste."
        in igual.get_data(as_text=True)
    )
    assert _stock(app, 6) == 20

    baja = _post_ajuste(client, 6, "18")
    assert _stock(app, 6) == 18
    assert _movimientos(app, 6)[1]["cantidad"] == -2
    assert _movimientos(app, 6)[1]["motivo"] == "DIFERENCIA_INVENTARIO"
    assert _movimientos(app, 6)[1]["unidad"] == "UNIDAD"

    _post_inicial_no = None
    alta = _post_ajuste(client, 6, "23")
    assert _stock(app, 6) == 23
    assert _movimientos(app, 6)[2]["cantidad"] == 5
    assert _movimientos(app, 6)[2]["motivo"] == "DIFERENCIA_INVENTARIO"


def test_ajuste_por_conteo_desde_veinte(client, app):
    _post_inicial(client, 6, "20")
    _post_ajuste(client, 6, "18")
    assert _movimientos(app, 6)[-1]["cantidad"] == -2

    _post_inicial(client, 1, "20")
    alta = _post_ajuste(client, 1, "23")
    assert "Stock ajustado correctamente." in alta.get_data(as_text=True)
    assert _stock(app, 1) == 23
    assert _movimientos(app, 1)[-1]["cantidad"] == 3
    assert _movimientos(app, 1)[-1]["motivo"] == "DIFERENCIA_INVENTARIO"


def test_ajuste_por_conteo_peso(client, app):
    _post_inicial(client, 3, "2", "KG")
    baja = _post_ajuste(client, 3, "1,8", unidad="KG")
    assert _stock(app, 3) == 1800
    assert _movimientos(app, 3)[-1]["cantidad"] == -200
    assert _movimientos(app, 3)[-1]["unidad"] == "G"
    assert _movimientos(app, 3)[-1]["motivo"] == "DIFERENCIA_INVENTARIO"

    alta = _post_ajuste(client, 3, "2,3", unidad="KG")
    assert _stock(app, 3) == 2300
    assert _movimientos(app, 3)[-1]["cantidad"] == 500
    assert _movimientos(app, 3)[-1]["motivo"] == "DIFERENCIA_INVENTARIO"


def test_descuento_unidad_veinte_menos_dos(client, app):
    _post_inicial(client, 6, "20")
    response = _post_descuento(client, 6, "2", "VENCIMIENTO")
    assert "Descuento registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 6) == 18
    movimiento = _movimientos(app, 6)[-1]
    assert movimiento["tipo"] == "AJUSTE"
    assert movimiento["cantidad"] == -2
    assert movimiento["unidad"] == "UNIDAD"
    assert movimiento["motivo"] == "VENCIMIENTO"
    html = client.get("/inventario/6/movimientos").get_data(as_text=True)
    assert "Vencimiento" in html
    assert "-2 unidades" in html
    assert "DIFERENCIA_INVENTARIO" not in html


def test_descuento_rechaza_cero_negativo_y_exceso(client, app):
    cero = _post_descuento(client, 2, "0", "ROTURA")
    assert "La cantidad a descontar debe ser mayor que cero." in cero.get_data(as_text=True)
    negativo = _post_descuento(client, 2, "-1", "ROTURA")
    assert "La cantidad no puede ser negativa." in negativo.get_data(as_text=True)
    exceso = _post_descuento(client, 2, "11", "MERMA")
    assert "No se puede descontar más que el stock actual." in exceso.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_descuento_peso_gramos_y_kilogramos(client, app):
    _post_inicial(client, 3, "250", "G")
    gramos = _post_descuento(client, 3, "100", "VENCIMIENTO", unidad="G")
    assert "Descuento registrado correctamente." in gramos.get_data(as_text=True)
    assert _stock(app, 3) == 150
    assert _movimientos(app, 3)[-1]["cantidad"] == -100
    assert _movimientos(app, 3)[-1]["unidad"] == "G"
    assert _movimientos(app, 3)[-1]["motivo"] == "VENCIMIENTO"
    html = client.get("/inventario/3/movimientos").get_data(as_text=True)
    assert "+250 g" in html
    assert "-100 g" in html
    assert "Vencimiento" in html


def test_descuento_peso_en_kilogramos_y_rechazos(client, app):
    _post_inicial(client, 3, "250", "G")
    kilos = _post_descuento(client, 3, "0,1", "VENCIMIENTO", unidad="KG")
    assert _stock(app, 3) == 150
    assert _movimientos(app, 3)[-1]["cantidad"] == -100

    _post_inicial_otro = _post_descuento(client, 3, "1,5", "MERMA", unidad="G")
    assert "La cantidad debe ser un número entero de gramos." in _post_inicial_otro.get_data(as_text=True)
    exceso = _post_descuento(client, 3, "1", "ROTURA", unidad="KG")
    assert "No se puede descontar más que el stock actual." in exceso.get_data(as_text=True)
    assert _stock(app, 3) == 150
    assert len(_movimientos(app, 3)) == 2


def test_descuento_inactivo_con_stock_y_sin_inicial(client, app):
    client.post("/productos/2/desactivar")
    response = _post_descuento(client, 2, "4", "CONSUMO_INTERNO")
    assert "Descuento registrado correctamente." in response.get_data(as_text=True)
    assert _stock(app, 2) == 6
    assert _movimientos(app, 2)[0]["motivo"] == "CONSUMO_INTERNO"
    assert _movimientos(app, 2)[0]["cantidad"] == -4
    with app.app_context():
        activo = get_db().execute(
            "SELECT activo FROM productos WHERE producto_id = 2"
        ).fetchone()[0]
    assert activo == 0

    detalle = client.get("/productos/2").get_data(as_text=True)
    assert "Descontar stock" in detalle
    assert "Ajustar stock" in detalle
    assert "Reponer stock" not in detalle
    assert "Registrar stock inicial" not in detalle

    sin_inicial = _post_descuento(client, 6, "1", "OTRO")
    assert "Primero registrá el stock inicial." in sin_inicial.get_data(as_text=True)
    assert _movimientos(app, 6) == []
    bloqueado = client.get("/inventario/6/descuento", follow_redirects=True)
    assert "Primero registrá el stock inicial." in bloqueado.get_data(as_text=True)


def test_descuento_no_acepta_diferencia_de_inventario(client, app):
    response = _post_descuento(client, 2, "1", "DIFERENCIA_INVENTARIO")
    assert "Elegí un motivo de descuento válido." in response.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []


def test_historial_separa_conteo_y_descuento(client):
    _post_inicial(client, 6, "20")
    _post_reposicion(client, 6, "10")
    _post_descuento(client, 6, "2", "VENCIMIENTO")
    _post_descuento(client, 6, "1", "ROTURA")
    _post_ajuste(client, 6, "30")
    primera = client.get("/inventario/6/movimientos").get_data(as_text=True)
    segunda = client.get("/inventario/6/movimientos?page=2").get_data(as_text=True)
    tercera = client.get("/inventario/6/movimientos?page=3").get_data(as_text=True)
    assert "Diferencia de inventario" in primera
    assert "+3 unidades" in primera
    assert "Rotura" in primera
    assert "-1 unidad" in primera
    assert "Vencimiento" in segunda
    assert "-2 unidades" in segunda
    assert "Reposición" in segunda
    assert "+10 unidades" in segunda
    assert "Stock inicial" in tercera
    assert "+20 unidades" in tercera


def test_invariante_incluye_descuento(client, app):
    _post_inicial(client, 6, "20")
    _post_reposicion(client, 6, "10")
    _post_descuento(client, 6, "2", "VENCIMIENTO")
    _post_ajuste(client, 6, "31")
    assert _suma(app, 6) == 31
    assert _stock(app, 6) == 31


def test_rollback_descuento_si_falla_insert(client, app, monkeypatch):
    orden = []
    repo = __import__("app.services.inventario", fromlist=["inventario_repo"]).inventario_repo
    actualizar = repo.actualizar_stock
    commit = __import__("app.services.inventario", fromlist=["commit_transaccion"]).commit_transaccion
    rollback = __import__("app.services.inventario", fromlist=["rollback_transaccion"]).rollback_transaccion

    def actualizar_vigilado(producto_id, stock):
        orden.append("update")
        return actualizar(producto_id, stock)

    def insertar_falla(**kwargs):
        orden.append("insert")
        raise sqlite3.IntegrityError("forzado")

    def commit_vigilado():
        orden.append("commit")
        return commit()

    def rollback_vigilado():
        orden.append("rollback")
        return rollback()

    monkeypatch.setattr(repo, "actualizar_stock", actualizar_vigilado)
    monkeypatch.setattr(repo, "insertar_movimiento", insertar_falla)
    monkeypatch.setattr("app.services.inventario.commit_transaccion", commit_vigilado)
    monkeypatch.setattr("app.services.inventario.rollback_transaccion", rollback_vigilado)

    response = _post_descuento(client, 2, "2", "VENCIMIENTO")
    assert "No se pudo guardar el movimiento de stock." in response.get_data(as_text=True)
    assert _stock(app, 2) == 10
    assert _movimientos(app, 2) == []
    assert orden == ["update", "insert", "rollback"]


def test_estados_visuales_de_stock():
    from app.services.inventario import _estado_de_stock

    assert _estado_de_stock(None, 5) == "Sin stock inicial"
    assert _estado_de_stock(0, 5) == "Sin existencias"
    assert _estado_de_stock(0, None) == "Sin existencias"
    assert _estado_de_stock(10, 5) == "Stock disponible"
    assert _estado_de_stock(10, None) == "Stock disponible"
    assert _estado_de_stock(3, 5) == "Stock bajo"
    assert _estado_de_stock(5, 5) == "Stock bajo"


def test_filtros_de_existencias_y_combinaciones(client):
    _post_inicial(client, 6, "0")
    _post_inicial(client, 1, "0")
    _post_ajuste(client, 2, "0")

    sin_inicial = client.get("/inventario?estado=sin_inicial&tipo=PESO&activo=activos").get_data(as_text=True)
    assert "QUESO CREMOSO" in sin_inicial
    assert "PAN DE MIGA" not in sin_inicial
    assert "AGUA MINERAL" not in sin_inicial

    sin_existencias = client.get("/inventario?estado=sin_existencias").get_data(as_text=True)
    assert "AGUA MINERAL" in sin_existencias
    assert "Sin existencias" in sin_existencias
    assert "COCA COLA 2.25L" in sin_existencias
    assert "PAN DE MIGA" not in sin_existencias
    assert "Stock disponible" not in sin_existencias

    con_existencias = client.get("/inventario?estado=con_existencias").get_data(as_text=True)
    assert "PAN DE MIGA" in con_existencias
    assert "Stock bajo" in con_existencias
    assert "AGUA MINERAL" not in con_existencias
    assert "COCA COLA 2.25L" not in con_existencias

    bajo = client.get("/inventario?estado=bajo").get_data(as_text=True)
    assert "PAN DE MIGA" in bajo
    assert "COCA COLA 2.25L" in bajo
    assert "AGUA MINERAL" not in bajo

    peso = client.get("/inventario?estado=con_existencias&tipo=PESO").get_data(as_text=True)
    assert "PAN DE MIGA" in peso
    assert "QUESO CREMOSO" not in peso
    assert "AGUA MINERAL" not in peso

    unidad = client.get("/inventario?estado=sin_existencias&tipo=UNIDAD").get_data(as_text=True)
    assert "AGUA MINERAL" in unidad
    assert "COCA COLA 2.25L" in unidad
    assert "PAN DE MIGA" not in unidad
    unidad_2 = client.get("/inventario?estado=sin_existencias&tipo=UNIDAD&page=2").get_data(as_text=True)
    assert "PRESERVATIVOS" in unidad_2

    busqueda = client.get("/inventario?q=AGUA&estado=sin_existencias").get_data(as_text=True)
    assert "AGUA MINERAL" in busqueda
    assert "COCA COLA 2.25L" not in busqueda

    inactivos = client.get("/inventario?estado=sin_inicial&activo=inactivos").get_data(as_text=True)
    assert "GALLETA INACTIVA" in inactivos
    assert "Registrar stock inicial" not in inactivos
    assert "Gestionar" in inactivos

    vacio = client.get("/inventario?estado=sin_existencias&activo=inactivos").get_data(as_text=True)
    assert "No se encontraron productos con los filtros seleccionados." in vacio
    assert "AGUA MINERAL" not in vacio


def test_paginacion_conserva_filtro_de_existencias(client):
    _post_inicial(client, 6, "0")
    _post_inicial(client, 1, "0")
    _post_ajuste(client, 2, "0")
    html = client.get("/inventario?estado=sin_existencias&tipo=UNIDAD&activo=activos").get_data(as_text=True)
    assert "estado=sin_existencias" in html
    assert "tipo=UNIDAD" in html
    assert "page=2" in html
    pagina2 = client.get(
        "/inventario?estado=sin_existencias&tipo=UNIDAD&activo=activos&page=2"
    ).get_data(as_text=True)
    assert "estado=sin_existencias" in pagina2
    assert "tipo=UNIDAD" in pagina2
    assert "activo=activos" in pagina2


def test_tabla_tiene_una_sola_accion_rapida(client):
    html = client.get("/inventario?q=AGUA").get_data(as_text=True)
    assert "Acción rápida" in html
    assert 'href="/productos/6' in html
    assert "Registrar stock inicial" in html
    assert "Gestionar" not in html
    assert "Reponer stock" not in html
    assert "Ajustar stock" not in html
    assert "Descontar stock" not in html
    assert "Ver movimientos" not in html
    assert "next=" in html

    inicializado = client.get("/inventario?q=COCA").get_data(as_text=True)
    assert "Gestionar" in inicializado
    assert 'href="/productos/2' in inicializado
    assert "Registrar stock inicial" not in inicializado
    assert "Reponer stock" not in inicializado
    assert "Ajustar stock" not in inicializado
    assert "Descontar stock" not in inicializado
    assert "Ver movimientos" not in inicializado
    assert "q%3DCOCA" in inicializado


def test_historial_separa_accion_y_motivo(client, app):
    from app.services.inventario import listar_movimientos

    _post_inicial(client, 6, "8")
    _post_reposicion(client, 6, "1")
    _post_descuento(client, 6, "1", "ROTURA")
    _post_descuento(client, 6, "1", "VENCIMIENTO")
    _post_descuento(client, 6, "1", "MERMA")
    _post_descuento(client, 6, "1", "CONSUMO_INTERNO")
    _post_descuento(client, 6, "1", "OTRO")
    _post_ajuste(client, 6, "6")

    with app.app_context():
        items = listar_movimientos(6, page=1, page_size=20)["items"]
    pares = {(item["accion"], item["motivo"]) for item in items}
    assert ("Stock inicial", "—") in pares
    assert ("Reposición", "—") in pares
    assert ("Ajuste por conteo", "Diferencia de inventario") in pares
    assert ("Descuento", "Rotura") in pares
    assert ("Descuento", "Vencimiento") in pares
    assert ("Descuento", "Merma") in pares
    assert ("Descuento", "Consumo interno") in pares
    assert ("Descuento", "Otro") in pares

    guardados = {fila["motivo"] for fila in _movimientos(app, 6)}
    assert guardados == {
        "STOCK_INICIAL",
        "REPOSICION",
        "ROTURA",
        "VENCIMIENTO",
        "MERMA",
        "CONSUMO_INTERNO",
        "OTRO",
        "DIFERENCIA_INVENTARIO",
    }
    html = client.get("/inventario/6/movimientos").get_data(as_text=True)
    assert "Ajuste por conteo" in html
    assert "Diferencia de inventario" in html
    assert "Descuento" in html
    assert "STOCK_INICIAL" not in html
    assert "DIFERENCIA_INVENTARIO" not in html
    assert "ROTURA" not in html
