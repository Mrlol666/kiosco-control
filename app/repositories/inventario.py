from __future__ import annotations

import sqlite3

from app.db import get_db


def _fila(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def obtener_producto(producto_id: int) -> dict | None:
    fila = get_db().execute(
        """
        SELECT
            producto_id,
            codigo_ean,
            descripcion,
            marca,
            tipo_venta,
            unidad_stock,
            stock_actual,
            stock_minimo,
            activo
        FROM productos
        WHERE producto_id = ?
        """,
        (producto_id,),
    ).fetchone()
    return _fila(fila)


def _condiciones(
    *,
    activo: int | None,
    estado_stock: str,
    tipo_venta: str | None,
    ean_exacto: str | None,
    like_pattern: str | None,
) -> tuple[str, list]:
    condiciones: list[str] = []
    params: list = []

    if activo is not None:
        condiciones.append("activo = ?")
        params.append(activo)

    if tipo_venta is not None:
        condiciones.append("tipo_venta = ?")
        params.append(tipo_venta)

    if ean_exacto is not None:
        condiciones.append("codigo_ean = ?")
        params.append(ean_exacto)
    elif like_pattern is not None:
        condiciones.append(
            "("
            "descripcion LIKE ? ESCAPE '!' "
            "OR marca LIKE ? ESCAPE '!' "
            "OR codigo_ean LIKE ? ESCAPE '!'"
            ")"
        )
        params.extend([like_pattern, like_pattern, like_pattern])

    if estado_stock == "sin_inicial":
        condiciones.append("stock_actual IS NULL")
    elif estado_stock == "sin_existencias":
        condiciones.append("stock_actual = 0")
    elif estado_stock == "con_existencias":
        condiciones.append("stock_actual > 0")
    elif estado_stock == "bajo":
        condiciones.append(
            "stock_actual IS NOT NULL "
            "AND stock_minimo IS NOT NULL "
            "AND stock_actual <= stock_minimo"
        )

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, params


def listar(
    *,
    activo: int | None,
    estado_stock: str,
    tipo_venta: str | None,
    ean_exacto: str | None,
    like_pattern: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    where, params = _condiciones(
        activo=activo,
        estado_stock=estado_stock,
        tipo_venta=tipo_venta,
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
    )
    params.extend([limit, offset])
    filas = get_db().execute(
        f"""
        SELECT
            producto_id,
            codigo_ean,
            descripcion,
            marca,
            tipo_venta,
            unidad_stock,
            stock_actual,
            stock_minimo,
            activo
        FROM productos
        {where}
        ORDER BY descripcion COLLATE NOCASE, producto_id
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    return [dict(fila) for fila in filas]


def contar(
    *,
    activo: int | None,
    estado_stock: str,
    tipo_venta: str | None,
    ean_exacto: str | None,
    like_pattern: str | None,
) -> int:
    where, params = _condiciones(
        activo=activo,
        estado_stock=estado_stock,
        tipo_venta=tipo_venta,
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
    )
    return get_db().execute(
        f"SELECT COUNT(*) AS total FROM productos {where}",
        params,
    ).fetchone()["total"]


def actualizar_stock(producto_id: int, stock_actual: int) -> None:
    cursor = get_db().execute(
        """
        UPDATE productos
        SET stock_actual = ?
        WHERE producto_id = ?
        """,
        (stock_actual, producto_id),
    )
    if cursor.rowcount != 1:
        raise sqlite3.Error("No se pudo actualizar el stock del producto.")


def insertar_movimiento(
    *,
    producto_id: int,
    fecha_hora: str,
    tipo: str,
    cantidad: int,
    unidad: str,
    motivo: str,
) -> int:
    cursor = get_db().execute(
        """
        INSERT INTO movimientos_stock (
            producto_id,
            fecha_hora,
            tipo,
            cantidad,
            unidad,
            motivo,
            venta_id
        ) VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (producto_id, fecha_hora, tipo, cantidad, unidad, motivo),
    )
    return int(cursor.lastrowid)


def listar_movimientos(producto_id: int, *, limit: int, offset: int) -> list[dict]:
    filas = get_db().execute(
        """
        SELECT
            movimiento_id,
            producto_id,
            fecha_hora,
            tipo,
            cantidad,
            unidad,
            motivo,
            venta_id
        FROM movimientos_stock
        WHERE producto_id = ?
        ORDER BY fecha_hora DESC, movimiento_id DESC
        LIMIT ? OFFSET ?
        """,
        (producto_id, limit, offset),
    ).fetchall()
    return [dict(fila) for fila in filas]


def contar_movimientos(producto_id: int) -> int:
    return get_db().execute(
        """
        SELECT COUNT(*) AS total
        FROM movimientos_stock
        WHERE producto_id = ?
        """,
        (producto_id,),
    ).fetchone()["total"]
