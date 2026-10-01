from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.forms import AccionProductoForm, ProductoEditarForm, ProductoNuevoForm
from app.navegacion import destino_o_fallback, url_actual, url_con_next
from app.services import inventario as inventario_service
from app.services import productos as productos_service
from app.services.productos import ProductoError

bp = Blueprint("productos", __name__, url_prefix="/productos")

CAMPOS_FORM = (
    "codigo_ean",
    "descripcion",
    "marca",
    "categoria",
    "tipo_venta",
    "precio_venta_actual",
    "precio_compra_actual",
    "stock_minimo",
)


def _datos_form(form) -> dict:
    return {campo: form.data.get(campo) for campo in CAMPOS_FORM if campo in form.data}


def _mostrar_errores(error: ProductoError) -> None:
    for mensaje in error.mensajes:
        flash(mensaje, "error")


def _redirigir(endpoint: str, **valores):
    return redirect(url_con_next(endpoint, **valores))


def _redirigir_o_listado():
    return redirect(destino_o_fallback(request.values.get("next"), url_for("productos.listado")))


def _valor_formulario(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


@bp.get("/")
def listado():
    resultado = productos_service.listar(
        q=request.args.get("q"),
        tipo=request.args.get("tipo"),
        estado=request.args.get("estado"),
        page=request.args.get("page"),
        page_size=current_app.config["PAGE_SIZE"],
    )
    return render_template("productos/list.html", retorno=url_actual(), **resultado)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    form = ProductoNuevoForm()
    if form.validate_on_submit():
        try:
            producto_id = productos_service.crear(_datos_form(form))
            flash("Producto agregado correctamente.", "ok")
            return _redirigir("productos.detalle", producto_id=producto_id)
        except ProductoError as error:
            _mostrar_errores(error)
    return render_template("productos/form.html", form=form, modo="nuevo", producto=None)


@bp.get("/<int:producto_id>")
def detalle(producto_id: int):
    producto = productos_service.obtener(producto_id)
    if producto is None:
        abort(404)
    return render_template(
        "productos/detail.html",
        producto=producto,
        accion_form=AccionProductoForm(),
        permisos=inventario_service.permisos(
            producto.get("stock_actual"),
            producto.get("activo"),
        ),
    )


@bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
def editar(producto_id: int):
    producto = productos_service.obtener(producto_id)
    if producto is None:
        abort(404)

    form = ProductoEditarForm()
    if request.method == "GET":
        form.descripcion.data = producto["descripcion"]
        form.marca.data = producto.get("marca") or ""
        form.categoria.data = producto.get("categoria") or ""
        form.tipo_venta.data = producto["tipo_venta"]
        form.precio_venta_actual.data = _valor_formulario(producto.get("precio_venta_actual"))
        form.precio_compra_actual.data = _valor_formulario(producto.get("precio_compra_actual"))
        form.stock_minimo.data = _valor_formulario(producto.get("stock_minimo"))

    if form.validate_on_submit():
        try:
            productos_service.editar(producto_id, _datos_form(form))
            flash("Producto actualizado correctamente.", "ok")
            return _redirigir("productos.detalle", producto_id=producto_id)
        except ProductoError as error:
            _mostrar_errores(error)

    return render_template(
        "productos/form.html",
        form=form,
        modo="editar",
        producto=producto,
    )


@bp.post("/<int:producto_id>/desactivar")
def desactivar(producto_id: int):
    form = AccionProductoForm()
    if not form.validate_on_submit():
        flash("No se pudo validar la acción.", "error")
        return _redirigir("productos.detalle", producto_id=producto_id)
    try:
        productos_service.desactivar(producto_id)
        flash("Producto desactivado.", "ok")
    except ProductoError as error:
        _mostrar_errores(error)
        return _redirigir_o_listado()
    return _redirigir("productos.detalle", producto_id=producto_id)


@bp.post("/<int:producto_id>/reactivar")
def reactivar(producto_id: int):
    form = AccionProductoForm()
    if not form.validate_on_submit():
        flash("No se pudo validar la acción.", "error")
        return _redirigir("productos.detalle", producto_id=producto_id)
    try:
        productos_service.reactivar(producto_id)
        flash("Producto reactivado.", "ok")
    except ProductoError as error:
        _mostrar_errores(error)
        return _redirigir_o_listado()
    return _redirigir("productos.detalle", producto_id=producto_id)
