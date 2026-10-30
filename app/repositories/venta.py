from __future__ import annotations

from app.db import get_db


def _fila(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def crear_carrito(creado_en: str) -> int:
    cursor = get_db().execute(
        """
        INSERT INTO carritos (estado, creado_en, pendiente_en, etiqueta)
        VALUES ('EN_CURSO', ?, NULL, NULL)
        """,
        (creado_en,),
    )
    return int(cursor.lastrowid)


def obtener_carrito(carrito_id: int) -> dict | None:
    return _fila(
        get_db()
        .execute(
            """
            SELECT carrito_id, estado, creado_en, pendiente_en, etiqueta
            FROM carritos
            WHERE carrito_id = ?
            """,
            (carrito_id,),
        )
        .fetchone()
    )


def contar_lineas(carrito_id: int) -> int:
    return int(
        get_db()
        .execute(
            "SELECT COUNT(*) AS total FROM carrito_lineas WHERE carrito_id = ?",
            (carrito_id,),
        )
        .fetchone()["total"]
    )


def obtener_linea(carrito_id: int, producto_id: int) -> dict | None:
    return _fila(
        get_db()
        .execute(
            """
            SELECT carrito_id, producto_id, cantidad
            FROM carrito_lineas
            WHERE carrito_id = ? AND producto_id = ?
            """,
            (carrito_id, producto_id),
        )
        .fetchone()
    )


def guardar_cantidad(carrito_id: int, producto_id: int, cantidad: float) -> None:
    get_db().execute(
        """
        INSERT INTO carrito_lineas (carrito_id, producto_id, cantidad)
        VALUES (?, ?, ?)
        ON CONFLICT(carrito_id, producto_id) DO UPDATE SET cantidad = excluded.cantidad
        """,
        (carrito_id, producto_id, cantidad),
    )


def quitar_linea(carrito_id: int, producto_id: int) -> None:
    get_db().execute(
        "DELETE FROM carrito_lineas WHERE carrito_id = ? AND producto_id = ?",
        (carrito_id, producto_id),
    )


def vaciar_lineas(carrito_id: int) -> None:
    get_db().execute(
        "DELETE FROM carrito_lineas WHERE carrito_id = ?",
        (carrito_id,),
    )


def listar_lineas(carrito_id: int) -> list[dict]:
    filas = get_db().execute(
        """
        SELECT
            lineas.producto_id,
            lineas.cantidad,
            productos.descripcion,
            productos.tipo_venta,
            productos.activo,
            productos.stock_actual,
            productos.precio_venta_actual
        FROM carrito_lineas AS lineas
        JOIN productos ON productos.producto_id = lineas.producto_id
        WHERE lineas.carrito_id = ?
        ORDER BY productos.descripcion COLLATE NOCASE, lineas.producto_id
        """,
        (carrito_id,),
    ).fetchall()
    return [dict(fila) for fila in filas]


def marcar_pendiente(carrito_id: int, pendiente_en: str, etiqueta: str | None) -> None:
    cursor = get_db().execute(
        """
        UPDATE carritos
        SET estado = 'PENDIENTE',
            pendiente_en = ?,
            etiqueta = COALESCE(?, etiqueta)
        WHERE carrito_id = ?
        """,
        (pendiente_en, etiqueta, carrito_id),
    )
    if cursor.rowcount != 1:
        raise LookupError("No se encontró el carrito.")


def marcar_en_curso(carrito_id: int) -> None:
    cursor = get_db().execute(
        """
        UPDATE carritos
        SET estado = 'EN_CURSO',
            pendiente_en = NULL
        WHERE carrito_id = ?
        """,
        (carrito_id,),
    )
    if cursor.rowcount != 1:
        raise LookupError("No se encontró el carrito.")


def listar_pendientes() -> list[dict]:
    filas = get_db().execute(
        """
        SELECT carrito_id, estado, creado_en, pendiente_en, etiqueta
        FROM carritos
        WHERE estado = 'PENDIENTE'
        ORDER BY pendiente_en, carrito_id
        """
    ).fetchall()
    return [dict(fila) for fila in filas]


def eliminar_carrito(carrito_id: int) -> None:
    get_db().execute("DELETE FROM carritos WHERE carrito_id = ?", (carrito_id,))


def buscar_productos(
    like_pattern: str | None,
    categoria: str | None,
    limite: int,
) -> list[dict]:
    condiciones = ["activo = 1"]
    params: list = []
    if like_pattern:
        condiciones.append("descripcion LIKE ? ESCAPE '!'")
        params.append(like_pattern)
    if categoria:
        condiciones.append("categoria = ?")
        params.append(categoria)
    if like_pattern is None and categoria is None:
        return []
    params.append(limite)
    filas = get_db().execute(
        f"""
        SELECT
            producto_id,
            descripcion,
            marca,
            categoria,
            tipo_venta,
            precio_venta_actual,
            stock_actual
        FROM productos
        WHERE {' AND '.join(condiciones)}
        ORDER BY descripcion COLLATE NOCASE, producto_id
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(fila) for fila in filas]


def listar_categorias() -> list[str]:
    filas = get_db().execute(
        """
        SELECT DISTINCT categoria
        FROM productos
        WHERE activo = 1
          AND categoria IS NOT NULL
          AND TRIM(categoria) != ''
        ORDER BY categoria COLLATE NOCASE
        """
    ).fetchall()
    return [fila["categoria"] for fila in filas]


def obtener_producto_para_venta(producto_id: int) -> dict | None:
    return _fila(
        get_db()
        .execute(
            """
            SELECT
                producto_id,
                descripcion,
                tipo_venta,
                activo,
                stock_actual,
                precio_venta_actual,
                precio_venta_confirmado,
                precio_compra_actual,
                unidad_stock
            FROM productos
            WHERE producto_id = ?
            """,
            (producto_id,),
        )
        .fetchone()
    )
