from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.forms import LineaVentaForm, PendienteVentaForm, PrecioVentaForm
from app.services import venta as venta_service
from app.services.venta import CLAVE_SESION, VentaError

bp = Blueprint("venta", __name__, url_prefix="/venta")


def _mensajes(error: VentaError) -> None:
    for mensaje in error.mensajes:
        flash(mensaje, "error")


def _activo() -> int:
    carrito_id = venta_service.asegurar_activo(session.get(CLAVE_SESION))
    session[CLAVE_SESION] = carrito_id
    return carrito_id


def _entero(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _confirmado(valor) -> bool:
    return str(valor or "").strip().lower() in {"1", "si", "sí", "true", "on"}


def _contexto_busqueda() -> dict:
    return {
        "q": (request.values.get("q") or "").strip(),
        "categoria": (request.values.get("categoria") or "").strip(),
        "vista": "pendientes" if request.values.get("vista") == "pendientes" else "actual",
    }


def _volver(**extra):
    datos = _contexto_busqueda()
    datos.update(extra)
    limpio = {clave: valor for clave, valor in datos.items() if valor not in (None, "")}
    return redirect(url_for("venta.inicio", **limpio))


@bp.get("/")
def inicio():
    carrito_id = _activo()
    contexto = _contexto_busqueda()
    try:
        carrito = venta_service.leer(carrito_id)
        pendientes = venta_service.listar_pendientes()
    except VentaError as error:
        _mensajes(error)
        carrito = None
        pendientes = []
    return render_template(
        "venta/index.html",
        carrito=carrito,
        pendientes=pendientes,
        busqueda=venta_service.buscar(contexto["q"], contexto["categoria"]),
        categorias=venta_service.listar_categorias(),
        form_linea=LineaVentaForm(),
        form_pendiente=PendienteVentaForm(),
        form_precio=PrecioVentaForm(),
        confirmar=request.args.get("confirmar") or "",
        pendiente_id=_entero(request.args.get("pendiente")),
        precio_id=_entero(request.args.get("precio")),
        **contexto,
    )


@bp.post("/lineas")
def agregar():
    carrito_id = _activo()
    form = LineaVentaForm()
    if form.validate_on_submit():
        producto_id = _entero(form.producto_id.data)
        if producto_id is None:
            flash("El producto no existe.", "error")
        else:
            try:
                venta_service.agregar_producto(
                    carrito_id,
                    producto_id,
                    form.cantidad.data or "1",
                )
                flash("Producto agregado.", "ok")
            except VentaError as error:
                _mensajes(error)
    return _volver(vista="actual")


@bp.post("/lineas/<int:producto_id>")
def editar(producto_id: int):
    carrito_id = _activo()
    form = LineaVentaForm()
    if form.validate_on_submit():
        try:
            venta_service.editar_cantidad(carrito_id, producto_id, form.cantidad.data)
            flash("Cantidad actualizada.", "ok")
        except VentaError as error:
            _mensajes(error)
    return _volver(vista="actual")


@bp.post("/lineas/<int:producto_id>/quitar")
def quitar(producto_id: int):
    carrito_id = _activo()
    form = LineaVentaForm()
    if form.validate_on_submit():
        try:
            venta_service.quitar_producto(carrito_id, producto_id)
            flash("Producto quitado.", "ok")
        except VentaError as error:
            _mensajes(error)
    return _volver(vista="actual")


@bp.post("/pendiente")
def dejar_pendiente():
    carrito_id = _activo()
    form = PendienteVentaForm()
    if form.validate_on_submit():
        try:
            session[CLAVE_SESION] = venta_service.dejar_pendiente(
                carrito_id, form.etiqueta.data
            )
            flash("Venta guardada como pendiente.", "ok")
        except VentaError as error:
            _mensajes(error)
    return _volver(vista="actual", q="", categoria="")


@bp.post("/pendientes/<int:carrito_id>/retomar")
def retomar(carrito_id: int):
    actual = _activo()
    form = PendienteVentaForm()
    if form.validate_on_submit():
        try:
            session[CLAVE_SESION] = venta_service.retomar(
                actual,
                carrito_id,
                confirmar=_confirmado(form.confirmar.data),
            )
            flash("Venta retomada.", "ok")
        except VentaError as error:
            _mensajes(error)
            return _volver(vista="pendientes")
    return _volver(vista="actual", q="", categoria="")


@bp.post("/pendientes/<int:carrito_id>/descartar")
def descartar(carrito_id: int):
    _activo()
    form = PendienteVentaForm()
    if form.validate_on_submit():
        try:
            venta_service.descartar_pendiente(
                carrito_id, confirmar=_confirmado(form.confirmar.data)
            )
            flash("Pendiente descartado.", "ok")
        except VentaError as error:
            _mensajes(error)
    return _volver(vista="pendientes")


@bp.post("/cancelar")
def cancelar():
    carrito_id = _activo()
    form = PendienteVentaForm()
    if form.validate_on_submit():
        try:
            venta_service.cancelar_activo(
                carrito_id, confirmar=_confirmado(form.confirmar.data)
            )
            flash("Carrito cancelado.", "ok")
        except VentaError as error:
            _mensajes(error)
    return _volver(vista="actual")


@bp.post("/precio")
def precio():
    _activo()
    form = PrecioVentaForm()
    if form.validate_on_submit():
        producto_id = _entero(form.producto_id.data)
        if producto_id is None:
            flash("El producto no existe.", "error")
        else:
            try:
                venta_service.actualizar_precio(producto_id, form.precio.data)
                flash("El precio se actualizó.", "ok")
            except VentaError as error:
                _mensajes(error)
    return _volver(vista="actual")
