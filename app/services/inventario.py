from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import ceil

from app.db import begin_immediate, commit_transaccion, rollback_transaccion
from app.repositories import inventario as inventario_repo
from app.services.productos import (
    format_cantidad,
    format_stock,
    format_tipo_venta,
    normalizar_pagina,
    normalizar_tipo,
    parece_ean_completo,
    patron_like,
)
from app.tiempo import ahora_local

MOTIVOS_DESCUENTO = {
    "ROTURA": "Rotura",
    "VENCIMIENTO": "Vencimiento",
    "MERMA": "Merma",
    "CONSUMO_INTERNO": "Consumo interno",
    "OTRO": "Otro",
}

ETIQUETAS_MOTIVO = {
    "STOCK_INICIAL": "Stock inicial",
    "REPOSICION": "Reposición",
    "DIFERENCIA_INVENTARIO": "Diferencia de inventario",
    **MOTIVOS_DESCUENTO,
}

ESTADOS_STOCK = {"todos", "sin_inicial", "sin_existencias", "con_existencias", "bajo"}
ALIAS_ESTADO_STOCK = {"con_stock": "con_existencias"}
ESTADOS_PRODUCTO = {"activos", "inactivos", "todos"}
UNIDADES_ENTRADA = {"G", "KG"}


class InventarioError(Exception):
    def __init__(self, mensajes: str | list[str]):
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        self.mensajes = mensajes
        super().__init__(" ".join(mensajes))


def permisos(stock_actual, activo) -> dict:
    inicializado = stock_actual is not None
    esta_activo = activo == 1
    return {
        "puede_inicial": esta_activo and not inicializado,
        "puede_reponer": esta_activo and inicializado,
        "puede_ajustar": inicializado,
        "puede_descontar": inicializado,
    }


def cantidad_interna(texto, tipo_venta: str, unidad_entrada: str | None, *, modo: str) -> int:
    numero = _decimal_usuario(texto, _mensaje_vacio(modo))
    if modo == "reposicion":
        if numero <= 0:
            raise InventarioError("La cantidad debe ser mayor que cero.")
    elif modo == "descuento":
        if numero < 0:
            raise InventarioError("La cantidad no puede ser negativa.")
        if numero == 0:
            raise InventarioError("La cantidad a descontar debe ser mayor que cero.")
    elif numero < 0:
        if modo == "ajuste":
            raise InventarioError("El stock real no puede ser negativo.")
        raise InventarioError("La cantidad no puede ser negativa.")

    if tipo_venta == "PESO":
        unidad = (unidad_entrada or "").strip().upper()
        if unidad not in UNIDADES_ENTRADA:
            raise InventarioError("Elegí gramos o kilogramos.")
        gramos = numero * Decimal("1000") if unidad == "KG" else numero
        if not _es_entero(gramos):
            raise InventarioError("La cantidad debe ser un número entero de gramos.")
        return int(gramos)

    if not _es_entero(numero):
        raise InventarioError("La cantidad debe ser un número entero de unidades.")
    return int(numero)


def listar(q=None, estado=None, activo=None, tipo=None, page=None, page_size=50) -> dict:
    consulta = (q or "").strip()
    estado_stock = _estado_stock(estado)
    estado_producto = _estado_producto(activo)
    tipo_norm = normalizar_tipo(tipo)
    tipo_sql = None if tipo_norm == "todos" else tipo_norm
    pagina = normalizar_pagina(page)
    tamanio = int(page_size) if int(page_size) > 0 else 50
    ean_exacto, like_pattern = _busqueda(consulta)
    activo_sql = _activo_sql(estado_producto)

    total = inventario_repo.contar(
        activo=activo_sql,
        estado_stock=estado_stock,
        tipo_venta=tipo_sql,
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
    )
    filas = inventario_repo.listar(
        activo=activo_sql,
        estado_stock=estado_stock,
        tipo_venta=tipo_sql,
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
        limit=tamanio,
        offset=(pagina - 1) * tamanio,
    )
    return {
        "items": [_presentar_producto(fila) for fila in filas],
        "total": total,
        "page": pagina,
        "page_size": tamanio,
        "total_pages": ceil(total / tamanio) if total else 0,
        "q": consulta,
        "estado": estado_stock,
        "activo": estado_producto,
        "tipo": tipo_norm,
    }


def obtener(producto_id: int) -> dict | None:
    fila = inventario_repo.obtener_producto(producto_id)
    if fila is None:
        return None
    return _presentar_producto(fila)


def listar_movimientos(producto_id: int, page=None, page_size=50) -> dict | None:
    producto = obtener(producto_id)
    if producto is None:
        return None
    pagina = normalizar_pagina(page)
    tamanio = int(page_size) if int(page_size) > 0 else 50
    total = inventario_repo.contar_movimientos(producto_id)
    filas = inventario_repo.listar_movimientos(
        producto_id,
        limit=tamanio,
        offset=(pagina - 1) * tamanio,
    )
    return {
        "producto": producto,
        "items": [
            _presentar_movimiento(fila, producto["tipo_venta"]) for fila in filas
        ],
        "total": total,
        "page": pagina,
        "page_size": tamanio,
        "total_pages": ceil(total / tamanio) if total else 0,
    }


def registrar_stock_inicial(producto_id: int, datos: dict) -> None:
    producto = _requerir_producto(producto_id)
    cantidad = cantidad_interna(
        datos.get("cantidad"),
        producto["tipo_venta"],
        datos.get("unidad_entrada"),
        modo="inicial",
    )
    tipo = producto["tipo_venta"]

    def operacion() -> None:
        actual = _requerir_producto(producto_id)
        _asegurar_mismo_tipo(actual, tipo)
        if actual["activo"] != 1:
            raise InventarioError(
                "Reactivá el producto antes de registrar el stock inicial."
            )
        if actual["stock_actual"] is not None:
            raise InventarioError("Este producto ya tiene stock inicial.")
        _guardar(
            producto_id=producto_id,
            stock=cantidad,
            tipo="AJUSTE",
            cantidad=cantidad,
            unidad=actual["unidad_stock"],
            motivo="STOCK_INICIAL",
        )

    _ejecutar(operacion)


def reponer(producto_id: int, datos: dict) -> None:
    producto = _requerir_producto(producto_id)
    cantidad = cantidad_interna(
        datos.get("cantidad"),
        producto["tipo_venta"],
        datos.get("unidad_entrada"),
        modo="reposicion",
    )
    tipo = producto["tipo_venta"]

    def operacion() -> None:
        actual = _requerir_producto(producto_id)
        _asegurar_mismo_tipo(actual, tipo)
        if actual["activo"] != 1:
            raise InventarioError(
                "Reactivá el producto antes de registrar una reposición."
            )
        if actual["stock_actual"] is None:
            raise InventarioError("Primero registrá el stock inicial.")
        nuevo = _entero_guardado(actual["stock_actual"]) + cantidad
        _guardar(
            producto_id=producto_id,
            stock=nuevo,
            tipo="ENTRADA",
            cantidad=cantidad,
            unidad=actual["unidad_stock"],
            motivo="REPOSICION",
        )

    _ejecutar(operacion)


def ajustar(producto_id: int, datos: dict) -> None:
    producto = _requerir_producto(producto_id)
    stock_real = cantidad_interna(
        datos.get("stock_real"),
        producto["tipo_venta"],
        datos.get("unidad_entrada"),
        modo="ajuste",
    )
    tipo = producto["tipo_venta"]

    def operacion() -> None:
        actual = _requerir_producto(producto_id)
        _asegurar_mismo_tipo(actual, tipo)
        if actual["stock_actual"] is None:
            raise InventarioError("Primero registrá el stock inicial.")
        registrado = _entero_guardado(actual["stock_actual"])
        diferencia = stock_real - registrado
        if diferencia == 0:
            raise InventarioError(
                "El stock real coincide con el stock registrado. "
                "No es necesario realizar un ajuste."
            )
        _guardar(
            producto_id=producto_id,
            stock=stock_real,
            tipo="AJUSTE",
            cantidad=diferencia,
            unidad=actual["unidad_stock"],
            motivo="DIFERENCIA_INVENTARIO",
        )

    _ejecutar(operacion)


def descontar(producto_id: int, datos: dict) -> None:
    producto = _requerir_producto(producto_id)
    cantidad = cantidad_interna(
        datos.get("cantidad"),
        producto["tipo_venta"],
        datos.get("unidad_entrada"),
        modo="descuento",
    )
    motivo = _motivo_descuento(datos.get("motivo"))
    tipo = producto["tipo_venta"]

    def operacion() -> None:
        actual = _requerir_producto(producto_id)
        _asegurar_mismo_tipo(actual, tipo)
        if actual["stock_actual"] is None:
            raise InventarioError("Primero registrá el stock inicial.")
        registrado = _entero_guardado(actual["stock_actual"])
        nuevo = registrado - cantidad
        if nuevo < 0:
            raise InventarioError("No se puede descontar más que el stock actual.")
        _guardar(
            producto_id=producto_id,
            stock=nuevo,
            tipo="AJUSTE",
            cantidad=-cantidad,
            unidad=actual["unidad_stock"],
            motivo=motivo,
        )

    _ejecutar(operacion)


def _ejecutar(operacion) -> None:
    begin_immediate()
    try:
        operacion()
        commit_transaccion()
    except InventarioError:
        rollback_transaccion()
        raise
    except Exception:
        rollback_transaccion()
        raise InventarioError("No se pudo guardar el movimiento de stock.") from None


def _guardar(
    *,
    producto_id: int,
    stock: int,
    tipo: str,
    cantidad: int,
    unidad: str,
    motivo: str,
) -> None:
    inventario_repo.actualizar_stock(producto_id, stock)
    inventario_repo.insertar_movimiento(
        producto_id=producto_id,
        fecha_hora=ahora_local(),
        tipo=tipo,
        cantidad=cantidad,
        unidad=unidad,
        motivo=motivo,
    )


def _requerir_producto(producto_id: int) -> dict:
    producto = inventario_repo.obtener_producto(producto_id)
    if producto is None:
        raise InventarioError("El producto no existe.")
    return producto


def _asegurar_mismo_tipo(producto: dict, tipo_venta: str) -> None:
    if producto["tipo_venta"] != tipo_venta:
        raise InventarioError("La forma de venta cambió. Volvé a intentar.")


def _motivo_descuento(valor) -> str:
    motivo = str(valor or "").strip().upper()
    if motivo not in MOTIVOS_DESCUENTO:
        raise InventarioError("Elegí un motivo de descuento válido.")
    return motivo


def _mensaje_vacio(modo: str) -> str:
    if modo == "ajuste":
        return "El stock real es obligatorio."
    if modo == "descuento":
        return "La cantidad a descontar es obligatoria."
    return "La cantidad es obligatoria."


def _decimal_usuario(texto, mensaje_vacio: str) -> Decimal:
    if texto is None:
        raise InventarioError(mensaje_vacio)
    limpio = str(texto).strip()
    if limpio == "":
        raise InventarioError(mensaje_vacio)
    if any(caracter.isspace() for caracter in limpio):
        raise InventarioError("La cantidad no es válida.")
    if limpio.startswith("+"):
        limpio = limpio[1:]
    negativo = limpio.startswith("-")
    if negativo:
        limpio = limpio[1:]
    if not limpio or not all(caracter.isdigit() or caracter in ",." for caracter in limpio):
        raise InventarioError("La cantidad no es válida.")
    if limpio.count(",") + limpio.count(".") > 1:
        raise InventarioError("La cantidad no es válida.")
    try:
        numero = Decimal(limpio.replace(",", "."))
    except InvalidOperation:
        raise InventarioError("La cantidad no es válida.") from None
    if negativo:
        numero = -numero
    return numero


def _es_entero(numero: Decimal) -> bool:
    return numero == numero.to_integral_value()


def _entero_guardado(valor) -> int:
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    if isinstance(valor, Decimal):
        numero = valor
    else:
        numero = Decimal(str(valor))
    if not _es_entero(numero):
        raise InventarioError("El stock registrado no es una cantidad entera.")
    return int(numero)


def _estado_stock(valor: str | None) -> str:
    if not valor:
        return "todos"
    texto = ALIAS_ESTADO_STOCK.get(valor.strip().lower(), valor.strip().lower())
    return texto if texto in ESTADOS_STOCK else "todos"


def _estado_producto(valor: str | None) -> str:
    if not valor:
        return "activos"
    texto = valor.strip().lower()
    return texto if texto in ESTADOS_PRODUCTO else "activos"


def _activo_sql(estado: str) -> int | None:
    if estado == "activos":
        return 1
    if estado == "inactivos":
        return 0
    return None


def _busqueda(consulta: str) -> tuple[str | None, str | None]:
    if not consulta:
        return None, None
    if parece_ean_completo(consulta):
        return consulta, None
    return None, patron_like(consulta)


def _estado_de_stock(stock_actual, stock_minimo) -> str:
    if stock_actual is None:
        return "Sin stock inicial"
    cantidad = _entero_guardado(stock_actual)
    if cantidad == 0:
        return "Sin existencias"
    if stock_minimo is not None and cantidad <= _entero_guardado(stock_minimo):
        return "Stock bajo"
    return "Stock disponible"


def _presentar_producto(fila: dict) -> dict:
    item = dict(fila)
    item["codigo_ean"] = str(item["codigo_ean"])
    tipo = item.get("tipo_venta")
    item["tipo_venta_mostrar"] = format_tipo_venta(tipo)
    item["stock_mostrar"] = format_stock(item.get("stock_actual"), tipo, es_stock_actual=True)
    item["stock_minimo_mostrar"] = format_stock(
        item.get("stock_minimo"), tipo, es_stock_actual=False
    )
    item["estado_stock"] = _estado_de_stock(item.get("stock_actual"), item.get("stock_minimo"))
    item["activo_mostrar"] = "Activo" if item.get("activo") == 1 else "Inactivo"
    item.update(permisos(item.get("stock_actual"), item.get("activo")))
    return item


def _etiqueta_motivo(motivo: str | None) -> str:
    if motivo in ETIQUETAS_MOTIVO:
        return ETIQUETAS_MOTIVO[motivo]
    if not motivo:
        return "—"
    return str(motivo).replace("_", " ")


def _cantidad_con_signo(cantidad: int, tipo_venta: str) -> str:
    texto = format_cantidad(abs(cantidad), tipo_venta)
    if cantidad > 0:
        return f"+{texto}"
    if cantidad < 0:
        return f"-{texto}"
    return texto


def _accion_y_motivo(tipo: str | None, motivo: str | None) -> tuple[str, str]:
    if motivo == "STOCK_INICIAL":
        return "Stock inicial", "—"
    if motivo == "REPOSICION" or tipo == "ENTRADA":
        return "Reposición", "—"
    if motivo == "DIFERENCIA_INVENTARIO":
        return "Ajuste por conteo", "Diferencia de inventario"
    if motivo in MOTIVOS_DESCUENTO:
        return "Descuento", MOTIVOS_DESCUENTO[motivo]
    return _etiqueta_motivo(motivo), "—"


def _presentar_movimiento(fila: dict, tipo_venta: str) -> dict:
    cantidad = _entero_guardado(fila["cantidad"])
    accion, motivo = _accion_y_motivo(fila.get("tipo"), fila.get("motivo"))
    return {
        "movimiento_id": fila["movimiento_id"],
        "fecha_hora": fila["fecha_hora"],
        "accion": accion,
        "motivo": motivo,
        "cantidad_mostrar": _cantidad_con_signo(cantidad, tipo_venta),
    }
