from __future__ import annotations

from app.db import get_db

COLUMNAS_LISTADO = """
    producto_id,
    codigo_ean,
    descripcion,
    marca,
    tipo_venta,
    unidad_stock,
    precio_venta_actual,
    stock_actual,
    calidad_dato,
    activo,
    origen_catalogo
"""

COLUMNAS_DETALLE = """
    producto_id,
    codigo_ean,
    descripcion,
    marca,
    categoria,
    tipo_venta,
    unidad_stock,
    precio_venta_actual,
    precio_venta_confirmado,
    precio_compra_actual,
    precio_compra_confirmado,
    stock_actual,
    stock_minimo,
    activo,
    origen_catalogo,
    calidad_dato,
    precio_venta_dia_28,
    precio_venta_dia_64,
    precio_venta_ref_min,
    precio_venta_ref_max,
    precio_venta_ref_promedio,
    precio_referencia_dia,
    precio_compra_referencia,
    alcance_precio_compra,
    mayorista_referencia,
    mayorista_sucursal_referencia,
    mayorista_localidad_referencia,
    unidad_venta_mayorista,
    precio_bulto_mayorista,
    fecha_minorista,
    fecha_mayorista
"""


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _armar_filtros(
    tipo_venta: str | None,
    activo: int | None,
    ean_exacto: str | None,
    like_pattern: str | None,
) -> tuple[str, list]:
    condiciones = []
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

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, params


def listar(
    *,
    tipo_venta: str | None = None,
    activo: int | None = None,
    ean_exacto: str | None = None,
    like_pattern: str | None = None,
    limit: int,
    offset: int,
) -> list[dict]:
    where, params = _armar_filtros(tipo_venta, activo, ean_exacto, like_pattern)
    sql = f"""
        SELECT {COLUMNAS_LISTADO}
        FROM productos
        {where}
        ORDER BY descripcion COLLATE NOCASE, producto_id
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    filas = get_db().execute(sql, params).fetchall()
    return [dict(fila) for fila in filas]


def contar(
    *,
    tipo_venta: str | None = None,
    activo: int | None = None,
    ean_exacto: str | None = None,
    like_pattern: str | None = None,
) -> int:
    where, params = _armar_filtros(tipo_venta, activo, ean_exacto, like_pattern)
    sql = f"SELECT COUNT(*) AS total FROM productos {where}"
    return get_db().execute(sql, params).fetchone()["total"]


def obtener_por_id(producto_id: int) -> dict | None:
    sql = f"""
        SELECT {COLUMNAS_DETALLE}
        FROM productos
        WHERE producto_id = ?
    """
    return _row_to_dict(get_db().execute(sql, (producto_id,)).fetchone())


def obtener_metricas() -> dict:
    sql = """
        SELECT
            SUM(CASE WHEN activo = 1 THEN 1 ELSE 0 END) AS activos,
            SUM(CASE WHEN activo = 0 THEN 1 ELSE 0 END) AS inactivos,
            SUM(CASE WHEN activo = 1 AND tipo_venta = 'UNIDAD' THEN 1 ELSE 0 END) AS unidad,
            SUM(CASE WHEN activo = 1 AND tipo_venta = 'PESO' THEN 1 ELSE 0 END) AS peso,
            SUM(CASE WHEN stock_actual IS NULL THEN 1 ELSE 0 END) AS sin_stock,
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
    fila = get_db().execute(sql).fetchone()
    datos = dict(fila) if fila else {}
    return {
        "activos": int(datos.get("activos") or 0),
        "inactivos": int(datos.get("inactivos") or 0),
        "unidad": int(datos.get("unidad") or 0),
        "peso": int(datos.get("peso") or 0),
        "sin_stock": int(datos.get("sin_stock") or 0),
        "stock_bajo": int(datos.get("stock_bajo") or 0),
    }


def existe_codigo(codigo_ean: str, excluir_id: int | None = None) -> bool:
    sql = "SELECT 1 FROM productos WHERE codigo_ean = ?"
    params: list = [codigo_ean]
    if excluir_id is not None:
        sql += " AND producto_id <> ?"
        params.append(excluir_id)
    sql += " LIMIT 1"
    return get_db().execute(sql, params).fetchone() is not None


def max_codigo_interno() -> str | None:
    sql = """
        SELECT codigo_ean
        FROM productos
        WHERE length(codigo_ean) = 13
          AND codigo_ean >= '9990000000001'
          AND codigo_ean <= '9999999999999'
        ORDER BY codigo_ean DESC
        LIMIT 1
    """
    fila = get_db().execute(sql).fetchone()
    return fila["codigo_ean"] if fila else None


def contar_historial(producto_id: int) -> dict:
    db = get_db()
    detalle = db.execute(
        "SELECT COUNT(*) AS total FROM detalle_venta WHERE producto_id = ?",
        (producto_id,),
    ).fetchone()["total"]
    movimientos = db.execute(
        "SELECT COUNT(*) AS total FROM movimientos_stock WHERE producto_id = ?",
        (producto_id,),
    ).fetchone()["total"]
    return {
        "detalle_venta": int(detalle),
        "movimientos_stock": int(movimientos),
        "total": int(detalle) + int(movimientos),
    }


def insertar(datos: dict) -> int:
    sql = """
        INSERT INTO productos (
            codigo_ean,
            descripcion,
            marca,
            categoria,
            tipo_venta,
            unidad_stock,
            precio_venta_actual,
            precio_venta_confirmado,
            precio_compra_actual,
            precio_compra_confirmado,
            stock_actual,
            stock_minimo,
            activo,
            origen_catalogo,
            calidad_dato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 1, 'MANUAL', 'MANUAL')
    """
    db = get_db()
    cursor = db.execute(
        sql,
        (
            datos["codigo_ean"],
            datos["descripcion"],
            datos["marca"],
            datos["categoria"],
            datos["tipo_venta"],
            datos["unidad_stock"],
            datos["precio_venta_actual"],
            datos["precio_venta_confirmado"],
            datos["precio_compra_actual"],
            datos["precio_compra_confirmado"],
            datos["stock_minimo"],
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def actualizar(producto_id: int, datos: dict) -> None:
    sql = """
        UPDATE productos
        SET descripcion = ?,
            marca = ?,
            categoria = ?,
            tipo_venta = ?,
            unidad_stock = ?,
            precio_venta_actual = ?,
            precio_venta_confirmado = ?,
            precio_compra_actual = ?,
            precio_compra_confirmado = ?,
            stock_minimo = ?
        WHERE producto_id = ?
    """
    db = get_db()
    db.execute(
        sql,
        (
            datos["descripcion"],
            datos["marca"],
            datos["categoria"],
            datos["tipo_venta"],
            datos["unidad_stock"],
            datos["precio_venta_actual"],
            datos["precio_venta_confirmado"],
            datos["precio_compra_actual"],
            datos["precio_compra_confirmado"],
            datos["stock_minimo"],
            producto_id,
        ),
    )
    db.commit()


def actualizar_activo(producto_id: int, activo: int) -> bool:
    db = get_db()
    cursor = db.execute(
        "UPDATE productos SET activo = ? WHERE producto_id = ?",
        (activo, producto_id),
    )
    db.commit()
    return cursor.rowcount > 0

