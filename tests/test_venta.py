import sqlite3

import pytest

from app.db import get_db
from app.services.venta import (
    CLAVE_SESION,
    VentaError,
    actualizar_precio,
    agregar_producto,
    asegurar_activo,
    cancelar_activo,
    dejar_pendiente,
    descartar_pendiente,
    editar_cantidad,
    leer,
    listar_pendientes,
    quitar_producto,
    retomar,
)


def _stock(app, producto_id: int):
    with app.app_context():
        return get_db().execute(
            "SELECT stock_actual FROM productos WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()[0]


def _producto(app, producto_id: int) -> dict:
    with app.app_context():
        return dict(
            get_db()
            .execute("SELECT * FROM productos WHERE producto_id = ?", (producto_id,))
            .fetchone()
        )


def _conteos(app) -> dict:
    with app.app_context():
        db = get_db()
        return {
            "ventas": db.execute("SELECT COUNT(*) AS total FROM ventas").fetchone()["total"],
            "detalle": db.execute("SELECT COUNT(*) AS total FROM detalle_venta").fetchone()["total"],
            "movimientos": db.execute(
                "SELECT COUNT(*) AS total FROM movimientos_stock"
            ).fetchone()["total"],
        }


def _fijar_stock(app, producto_id: int, stock) -> None:
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE productos SET stock_actual = ? WHERE producto_id = ?",
            (stock, producto_id),
        )
        db.commit()


def _carrito_con_coca(app) -> int:
    with app.app_context():
        carrito_id = asegurar_activo(None)
        agregar_producto(carrito_id, 2, "2")
        return carrito_id


def test_puede_haber_varios_carritos_en_curso(app):
    with app.app_context():
        primero = asegurar_activo(None)
        segundo = asegurar_activo(None)
        estados = get_db().execute(
            "SELECT estado FROM carritos ORDER BY carrito_id"
        ).fetchall()
    assert primero != segundo
    assert [fila["estado"] for fila in estados] == ["EN_CURSO", "EN_CURSO"]


def test_agregar_incrementar_editar_quitar_y_totales(app):
    _fijar_stock(app, 6, 4)
    with app.app_context():
        carrito_id = asegurar_activo(None)
        agregar_producto(carrito_id, 2, "2")
        agregar_producto(carrito_id, 2, "1")
        agregar_producto(carrito_id, 6, "1")
        lectura = leer(carrito_id)
        assert [linea["cantidad"] for linea in lectura["lineas"]] == [1, 3]
        assert lectura["lineas"][1]["subtotal"] == 7500
        assert lectura["lineas"][0]["subtotal"] == 800
        assert lectura["total"] == 8300

        editar_cantidad(carrito_id, 2, "4")
        assert leer(carrito_id)["lineas"][1]["cantidad"] == 4
        assert leer(carrito_id)["lineas"][1]["subtotal"] == 10000

        quitar_producto(carrito_id, 6)
        lectura = leer(carrito_id)
        assert len(lectura["lineas"]) == 1
        assert lectura["total"] == 10000

        cancelar_activo(carrito_id, confirmar=True)
        vacio = leer(carrito_id)
        assert vacio["lineas"] == []
        assert vacio["total"] == 0
        assert vacio["carrito_id"] == carrito_id
        assert vacio["estado"] == "EN_CURSO"


def test_cancelar_sin_confirmacion_no_vacia(app):
    carrito_id = _carrito_con_coca(app)
    with app.app_context():
        with pytest.raises(VentaError, match="Confirmá"):
            cancelar_activo(carrito_id, confirmar=False)
        assert len(leer(carrito_id)["lineas"]) == 1


@pytest.mark.parametrize(
    ("producto_id", "cantidad", "fragmento"),
    [
        (9999, "1", "no existe"),
        (4, "1", "inactivo"),
        (1, "1", "Stock sin inicializar"),
        (3, "1", "próxima versión"),
        (2, "0", "mayor que cero"),
        (2, "-1", "no puede ser negativa"),
        (2, "1.5", "número entero"),
        (2, "1,5", "número entero"),
        (2, "11", "No hay suficiente stock"),
    ],
)
def test_validaciones_al_agregar(app, producto_id, cantidad, fragmento):
    with app.app_context():
        carrito_id = asegurar_activo(None)
        with pytest.raises(VentaError, match=fragmento):
            agregar_producto(carrito_id, producto_id, cantidad)
        assert leer(carrito_id)["lineas"] == []


def test_stock_cero_no_se_agrega(app):
    _fijar_stock(app, 2, 0)
    with app.app_context():
        carrito_id = asegurar_activo(None)
        with pytest.raises(VentaError, match="Sin existencias"):
            agregar_producto(carrito_id, 2, "1")
        assert leer(carrito_id)["lineas"] == []


def test_incrementar_no_supera_el_stock(app):
    with app.app_context():
        carrito_id = asegurar_activo(None)
        agregar_producto(carrito_id, 2, "8")
        with pytest.raises(VentaError, match="No hay suficiente stock"):
            agregar_producto(carrito_id, 2, "3")
        assert leer(carrito_id)["lineas"][0]["cantidad"] == 8


def test_el_carrito_no_toca_stock_ni_ventas(app):
    carrito_id = _carrito_con_coca(app)
    with app.app_context():
        editar_cantidad(carrito_id, 2, "3")
        quitar_producto(carrito_id, 2)
        agregar_producto(carrito_id, 2, "1")
        nuevo = dejar_pendiente(carrito_id)
        retomar(nuevo, carrito_id, confirmar=False)
        cancelar_activo(carrito_id, confirmar=True)
    assert _stock(app, 2) == 10
    assert _conteos(app) == {"ventas": 0, "detalle": 0, "movimientos": 0}


def test_dejar_pendiente_vacio_no_cambia_nada(app):
    with app.app_context():
        carrito_id = asegurar_activo(None)
        with pytest.raises(VentaError, match="vacío"):
            dejar_pendiente(carrito_id)
        assert leer(carrito_id)["estado"] == "EN_CURSO"
        assert get_db().execute("SELECT COUNT(*) AS total FROM carritos").fetchone()["total"] == 1


def test_pendiente_conserva_lineas_hora_y_nuevo_activo(app, monkeypatch):
    marcas = iter(["2026-10-19 18:00:00", "2026-10-19 18:04:00", "2026-10-19 18:04:00"])
    monkeypatch.setattr("app.services.venta.ahora_local", lambda: next(marcas))
    with app.app_context():
        carrito_id = asegurar_activo(None)
        agregar_producto(carrito_id, 2, "2")
        nuevo = dejar_pendiente(carrito_id, "Juan")
        pendiente = leer(carrito_id)
        assert pendiente["estado"] == "PENDIENTE"
        assert pendiente["pendiente_en"] == "2026-10-19 18:04:00"
        assert pendiente["etiqueta"] == "Juan"
        assert pendiente["lineas"][0]["cantidad"] == 2
        assert leer(nuevo)["estado"] == "EN_CURSO"
        assert leer(nuevo)["lineas"] == []
        listado = listar_pendientes()
    assert listado[0]["carrito_id"] == carrito_id
    assert listado[0]["pendiente_en"] == "2026-10-19 18:04:00"
    assert listado[0]["resumen"] == ["COCA COLA 2.25L"]


def test_retomar_con_activo_vacio(app):
    with app.app_context():
        carrito_id = asegurar_activo(None)
        agregar_producto(carrito_id, 2, "2")
        nuevo = dejar_pendiente(carrito_id)
        retomado = retomar(nuevo, carrito_id, confirmar=False)
        assert retomado == carrito_id
        assert leer(carrito_id)["estado"] == "EN_CURSO"
        assert leer(carrito_id)["pendiente_en"] is None
        assert leer(carrito_id)["lineas"][0]["cantidad"] == 2
        assert get_db().execute("SELECT COUNT(*) AS total FROM carritos").fetchone()["total"] == 1


def test_retomar_con_activo_ocupado_exige_confirmacion(app, monkeypatch):
    marcas = iter(
        [
            "2026-10-19 18:00:00",
            "2026-10-19 18:04:00",
            "2026-10-19 18:04:00",
            "2026-10-19 18:10:00",
        ]
    )
    monkeypatch.setattr("app.services.venta.ahora_local", lambda: next(marcas))
    _fijar_stock(app, 6, 3)
    with app.app_context():
        primero = asegurar_activo(None)
        agregar_producto(primero, 2, "1")
        actual = dejar_pendiente(primero)
        agregar_producto(actual, 6, "1")
        with pytest.raises(VentaError, match="dejarla pendiente"):
            retomar(actual, primero, confirmar=False)
        assert leer(actual)["estado"] == "EN_CURSO"
        assert leer(primero)["estado"] == "PENDIENTE"

        retomado = retomar(actual, primero, confirmar=True)
        assert retomado == primero
        assert leer(primero)["estado"] == "EN_CURSO"
        assert leer(primero)["lineas"][0]["producto_id"] == 2
        assert leer(actual)["estado"] == "PENDIENTE"
        assert leer(actual)["pendiente_en"] == "2026-10-19 18:10:00"
        assert leer(actual)["lineas"][0]["producto_id"] == 6


def test_descartar_pendiente_no_afecta_el_activo_ni_el_stock(app):
    with app.app_context():
        pendiente = asegurar_activo(None)
        agregar_producto(pendiente, 2, "2")
        activo = dejar_pendiente(pendiente)
        agregar_producto(activo, 2, "1")
        with pytest.raises(VentaError, match="Confirmá"):
            descartar_pendiente(pendiente, confirmar=False)
        assert leer(pendiente)["estado"] == "PENDIENTE"
        descartar_pendiente(pendiente, confirmar=True)
        assert leer(activo)["estado"] == "EN_CURSO"
        assert leer(activo)["lineas"][0]["cantidad"] == 1
        with pytest.raises(VentaError, match="no existe"):
            leer(pendiente)
    assert _stock(app, 2) == 10
    assert _conteos(app) == {"ventas": 0, "detalle": 0, "movimientos": 0}


def test_stock_cambiado_en_un_pendiente_se_detecta_sin_corregir_la_cantidad(app):
    carrito_id = _carrito_con_coca(app)
    with app.app_context():
        dejar_pendiente(carrito_id)
    _fijar_stock(app, 2, 1)
    with app.app_context():
        lectura = leer(carrito_id)
    assert lectura["lineas"][0]["cantidad"] == 2
    assert lectura["lineas"][0]["aviso_stock"] == "Pediste 2. Ahora hay 1 disponible."


def test_actualizar_precio_solo_cambia_el_precio_de_venta(app):
    carrito_id = _carrito_con_coca(app)
    antes = _producto(app, 2)
    with app.app_context():
        actualizar_precio(2, "3000")
        lectura = leer(carrito_id)
    despues = _producto(app, 2)
    assert despues["precio_venta_actual"] == 3000
    assert despues["precio_venta_confirmado"] == 1
    assert despues["precio_compra_actual"] == antes["precio_compra_actual"]
    assert despues["descripcion"] == antes["descripcion"]
    assert despues["tipo_venta"] == antes["tipo_venta"]
    assert despues["stock_actual"] == antes["stock_actual"]
    assert lectura["lineas"][0]["precio_venta_actual"] == 3000
    assert lectura["lineas"][0]["subtotal"] == 6000
    assert lectura["total"] == 6000


def test_precio_negativo_no_cambia_el_producto(app):
    antes = _producto(app, 2)
    with app.app_context():
        with pytest.raises(VentaError, match="no puede ser negativo"):
            actualizar_precio(2, "-5")
    assert _producto(app, 2)["precio_venta_actual"] == antes["precio_venta_actual"]
    assert _producto(app, 2)["precio_venta_confirmado"] == antes["precio_venta_confirmado"]


def test_dejar_pendiente_se_revierte_si_falla_el_alta_del_nuevo(app, monkeypatch):
    from app.repositories import venta as venta_repo

    carrito_id = _carrito_con_coca(app)

    def crear_falla(creado_en: str) -> int:
        raise sqlite3.OperationalError("forzado")

    monkeypatch.setattr(venta_repo, "crear_carrito", crear_falla)
    monkeypatch.setattr("app.services.venta.venta_repo.crear_carrito", crear_falla)
    with app.app_context():
        with pytest.raises(VentaError, match="No se pudo guardar"):
            dejar_pendiente(carrito_id)
        assert leer(carrito_id)["estado"] == "EN_CURSO"
        assert leer(carrito_id)["lineas"][0]["cantidad"] == 2
        assert get_db().execute("SELECT COUNT(*) AS total FROM carritos").fetchone()["total"] == 1


def test_la_sesion_solo_guarda_el_id_del_carrito_activo(client, app):
    client.get("/venta")
    with client.session_transaction() as sesion:
        assert CLAVE_SESION in sesion
        assert set(sesion.keys()) <= {CLAVE_SESION, "csrf_token"}
        carrito_id = sesion[CLAVE_SESION]
    respuesta = client.post(
        "/venta/lineas",
        data={"producto_id": "2", "cantidad": "1"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 302
    with client.session_transaction() as sesion:
        assert set(sesion.keys()) <= {CLAVE_SESION, "csrf_token", "_flashes"}
        assert sesion[CLAVE_SESION] == carrito_id
        assert "lineas" not in sesion
        assert "precio" not in sesion
        assert "stock" not in sesion
    with app.app_context():
        lectura = leer(carrito_id)
    assert lectura["lineas"][0]["cantidad"] == 1
    assert _stock(app, 2) == 10
