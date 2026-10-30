from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.db import begin_immediate, commit_transaccion, rollback_transaccion
from app.repositories import venta as venta_repo
from app.services.productos import (
    ProductoError,
    actualizar_precio_venta,
    format_precio,
    patron_like,
)
from app.tiempo import ahora_local

CLAVE_SESION = "carrito_activo_id"


class VentaError(Exception):
    def __init__(self, mensajes: str | list[str]):
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        self.mensajes = mensajes
        super().__init__(" ".join(mensajes))


def asegurar_activo(carrito_id) -> int:
    identificador = _identificador(carrito_id)
    if identificador is not None:
        carrito = venta_repo.obtener_carrito(identificador)
        if carrito is not None and carrito["estado"] == "EN_CURSO":
            return identificador
    nuevo = venta_repo.crear_carrito(ahora_local())
    commit_transaccion()
    return nuevo


def agregar_producto(carrito_id: int, producto_id: int, cantidad) -> None:
    pedida = _cantidad_unidad(cantidad)

    def operacion() -> None:
        _requerir_en_curso(carrito_id)
        producto = _producto_en_transaccion(producto_id)
        _validar_vendible(producto)
        actual = venta_repo.obtener_linea(carrito_id, producto_id)
        acumulada = pedida if actual is None else _entero(actual["cantidad"]) + pedida
        _validar_stock(producto, acumulada)
        venta_repo.guardar_cantidad(carrito_id, producto_id, acumulada)

    _ejecutar(operacion)


def editar_cantidad(carrito_id: int, producto_id: int, cantidad) -> None:
    pedida = _cantidad_unidad(cantidad)

    def operacion() -> None:
        _requerir_en_curso(carrito_id)
        if venta_repo.obtener_linea(carrito_id, producto_id) is None:
            raise VentaError("Ese producto no está en el carrito.")
        producto = _producto_en_transaccion(producto_id)
        _validar_vendible(producto)
        _validar_stock(producto, pedida)
        venta_repo.guardar_cantidad(carrito_id, producto_id, pedida)

    _ejecutar(operacion)


def quitar_producto(carrito_id: int, producto_id: int) -> None:
    def operacion() -> None:
        _requerir_en_curso(carrito_id)
        venta_repo.quitar_linea(carrito_id, producto_id)

    _ejecutar(operacion)


def cancelar_activo(carrito_id: int, *, confirmar: bool) -> None:
    if not confirmar:
        raise VentaError("Confirmá si querés cancelar la venta actual.")

    def operacion() -> None:
        _requerir_en_curso(carrito_id)
        venta_repo.vaciar_lineas(carrito_id)

    _ejecutar(operacion)


def dejar_pendiente(carrito_id: int, etiqueta=None) -> int:
    texto = _etiqueta(etiqueta)

    def operacion() -> int:
        _requerir_en_curso(carrito_id)
        if venta_repo.contar_lineas(carrito_id) == 0:
            raise VentaError("El carrito está vacío. No hay una venta para dejar pendiente.")
        venta_repo.marcar_pendiente(carrito_id, ahora_local(), texto)
        return venta_repo.crear_carrito(ahora_local())

    return _ejecutar(operacion)


def listar_pendientes() -> list[dict]:
    return [_resumen_pendiente(fila) for fila in venta_repo.listar_pendientes()]


def retomar(carrito_actual_id: int, pendiente_id: int, *, confirmar: bool) -> int:
    def operacion() -> int:
        _requerir_en_curso(carrito_actual_id)
        pendiente = venta_repo.obtener_carrito(pendiente_id)
        if pendiente is None or pendiente["estado"] != "PENDIENTE":
            raise VentaError("Ese carrito pendiente no existe.")
        if pendiente_id == carrito_actual_id:
            raise VentaError("Ese carrito ya es la venta actual.")
        vacio = venta_repo.contar_lineas(carrito_actual_id) == 0
        if not vacio and not confirmar:
            raise VentaError(
                "La venta actual tiene productos. "
                "Confirmá si querés dejarla pendiente y abrir la otra."
            )
        if vacio:
            venta_repo.eliminar_carrito(carrito_actual_id)
        else:
            venta_repo.marcar_pendiente(carrito_actual_id, ahora_local(), None)
        venta_repo.marcar_en_curso(pendiente_id)
        return pendiente_id

    return _ejecutar(operacion)


def descartar_pendiente(pendiente_id: int, *, confirmar: bool) -> None:
    if not confirmar:
        raise VentaError("Confirmá si querés descartar este pendiente.")

    def operacion() -> None:
        pendiente = venta_repo.obtener_carrito(pendiente_id)
        if pendiente is None or pendiente["estado"] != "PENDIENTE":
            raise VentaError("Ese carrito pendiente no existe.")
        venta_repo.eliminar_carrito(pendiente_id)

    _ejecutar(operacion)


def actualizar_precio(producto_id: int, precio) -> None:
    try:
        actualizar_precio_venta(producto_id, precio)
    except ProductoError as error:
        raise VentaError(error.mensajes) from None


def buscar(q=None, categoria=None, limite: int = 20) -> dict:
    consulta = (q or "").strip()
    categoria_texto = (categoria or "").strip()
    if not consulta and not categoria_texto:
        return {"resultados": [], "recortado": False, "q": "", "categoria": ""}
    filas = venta_repo.buscar_productos(
        patron_like(consulta) if consulta else None,
        categoria_texto or None,
        limite + 1,
    )
    recortado = len(filas) > limite
    items = [_presentar_busqueda(fila) for fila in filas[:limite]]
    return {
        "resultados": items,
        "recortado": recortado,
        "q": consulta,
        "categoria": categoria_texto,
    }


def listar_categorias() -> list[str]:
    return venta_repo.listar_categorias()


def leer(carrito_id: int) -> dict:
    carrito = venta_repo.obtener_carrito(carrito_id)
    if carrito is None:
        raise VentaError("El carrito no existe.")
    lineas = [_presentar_linea(fila) for fila in venta_repo.listar_lineas(carrito_id)]
    total = sum(linea["subtotal"] for linea in lineas)
    return {
        "carrito_id": carrito["carrito_id"],
        "estado": carrito["estado"],
        "creado_en": carrito["creado_en"],
        "pendiente_en": carrito["pendiente_en"],
        "etiqueta": carrito["etiqueta"],
        "lineas": lineas,
        "total": total,
        "total_mostrar": format_precio(total),
        "requiere_correccion": any(linea["aviso_stock"] for linea in lineas),
    }


def _ejecutar(operacion):
    begin_immediate()
    try:
        resultado = operacion()
        commit_transaccion()
        return resultado
    except VentaError:
        rollback_transaccion()
        raise
    except Exception:
        rollback_transaccion()
        raise VentaError("No se pudo guardar el carrito.") from None


def _requerir_en_curso(carrito_id: int) -> dict:
    carrito = venta_repo.obtener_carrito(carrito_id)
    if carrito is None or carrito["estado"] != "EN_CURSO":
        raise VentaError("No hay una venta en curso válida.")
    return carrito


def _producto_en_transaccion(producto_id: int) -> dict:
    producto = venta_repo.obtener_producto_para_venta(producto_id)
    if producto is None:
        raise VentaError("El producto no existe.")
    return producto


def _validar_vendible(producto: dict) -> None:
    if producto["activo"] != 1:
        raise VentaError("Este producto está inactivo.")
    if producto["tipo_venta"] != "UNIDAD":
        raise VentaError("Venta por peso disponible en una próxima versión.")
    if producto["precio_venta_actual"] is None:
        raise VentaError("Este producto no tiene un precio de venta.")


def _validar_stock(producto: dict, cantidad: int) -> None:
    if producto["stock_actual"] is None:
        raise VentaError("Stock sin inicializar.")
    disponible = _entero(producto["stock_actual"])
    if disponible <= 0:
        raise VentaError("Sin existencias.")
    if cantidad > disponible:
        raise VentaError(f"No hay suficiente stock. Hay {disponible} y pediste {cantidad}.")


def _presentar_linea(fila: dict) -> dict:
    cantidad = _entero(fila["cantidad"])
    precio = fila["precio_venta_actual"]
    subtotal = 0.0 if precio is None else float(Decimal(str(precio)) * Decimal(cantidad))
    return {
        "producto_id": fila["producto_id"],
        "descripcion": fila["descripcion"],
        "cantidad": cantidad,
        "precio_venta_actual": None if precio is None else float(precio),
        "precio_mostrar": format_precio(precio),
        "stock_actual": None if fila["stock_actual"] is None else _entero(fila["stock_actual"]),
        "subtotal": subtotal,
        "subtotal_mostrar": format_precio(subtotal),
        "aviso_stock": _aviso_stock(cantidad, fila["stock_actual"]),
    }


def _aviso_stock(cantidad: int, stock_actual) -> str | None:
    if stock_actual is None:
        return f"Pediste {cantidad} y ahora el stock está sin inicializar."
    disponible = _entero(stock_actual)
    if cantidad > disponible:
        return f"Pediste {cantidad}. Ahora hay {disponible} disponible."
    return None


def _resumen_pendiente(carrito: dict) -> dict:
    lectura = leer(carrito["carrito_id"])
    return {
        "carrito_id": carrito["carrito_id"],
        "pendiente_en": carrito["pendiente_en"],
        "etiqueta": carrito["etiqueta"],
        "total": lectura["total"],
        "total_mostrar": lectura["total_mostrar"],
        "titulo": _titulo_pendiente(carrito.get("etiqueta"), carrito.get("pendiente_en")),
        "resumen": [linea["descripcion"] for linea in lectura["lineas"][:3]],
        "restantes": max(0, len(lectura["lineas"]) - 3),
        "lineas": lectura["lineas"],
        "requiere_correccion": lectura["requiere_correccion"],
    }


def _titulo_pendiente(etiqueta: str | None, pendiente_en: str | None) -> str:
    if etiqueta:
        return etiqueta
    if pendiente_en and len(pendiente_en) >= 16:
        return f"Pendiente {pendiente_en[11:16]}"
    return "Pendiente"


def _bloqueo_busqueda(producto: dict) -> str | None:
    if producto["tipo_venta"] != "UNIDAD":
        return "Venta por peso disponible en una próxima versión"
    if producto["precio_venta_actual"] is None:
        return "Producto sin precio de venta"
    if producto["stock_actual"] is None:
        return "Stock sin inicializar"
    if _entero(producto["stock_actual"]) <= 0:
        return "Sin existencias"
    return None


def _presentar_busqueda(fila: dict) -> dict:
    bloqueo = _bloqueo_busqueda(fila)
    stock = None if fila["stock_actual"] is None else _entero(fila["stock_actual"])
    return {
        "producto_id": fila["producto_id"],
        "descripcion": fila["descripcion"],
        "marca": fila["marca"] or "",
        "precio_mostrar": format_precio(fila["precio_venta_actual"]),
        "stock_actual": stock,
        "puede_agregar": bloqueo is None,
        "bloqueo": bloqueo,
    }


def _cantidad_unidad(valor) -> int:
    if valor is None or str(valor).strip() == "":
        raise VentaError("La cantidad es obligatoria.")
    limpio = str(valor).strip().replace(",", ".")
    if limpio.startswith("+"):
        limpio = limpio[1:]
    negativo = limpio.startswith("-")
    if negativo:
        limpio = limpio[1:]
    try:
        numero = Decimal(limpio)
    except InvalidOperation:
        raise VentaError("La cantidad no es válida.") from None
    if negativo or numero < 0:
        raise VentaError("La cantidad no puede ser negativa.")
    if numero == 0:
        raise VentaError("La cantidad debe ser mayor que cero.")
    if numero != numero.to_integral_value():
        raise VentaError("La cantidad debe ser un número entero de unidades.")
    return int(numero)


def _entero(valor) -> int:
    numero = Decimal(str(valor))
    if numero != numero.to_integral_value():
        raise VentaError("La cantidad registrada no es un número entero.")
    return int(numero)


def _identificador(valor) -> int | None:
    if valor is None or valor is False:
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero <= 0:
        return None
    return numero


def _etiqueta(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None
