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

from app.forms import AjusteForm, DescuentoForm, ReposicionForm, StockInicialForm
from app.navegacion import url_actual, url_con_next
from app.services import inventario as inventario_service
from app.services.inventario import InventarioError

bp = Blueprint("inventario", __name__, url_prefix="/inventario")


def _producto_o_404(producto_id: int) -> dict:
    producto = inventario_service.obtener(producto_id)
    if producto is None:
        abort(404)
    return producto


def _mostrar_errores(error: InventarioError) -> None:
    for mensaje in error.mensajes:
        flash(mensaje, "error")


def _datos_cantidad(form) -> dict:
    return {
        "cantidad": form.cantidad.data,
        "unidad_entrada": form.unidad_entrada.data,
    }


def _redirigir(endpoint: str, **valores):
    return redirect(url_con_next(endpoint, **valores))


@bp.get("/")
def listado():
    resultado = inventario_service.listar(
        q=request.args.get("q"),
        estado=request.args.get("estado"),
        activo=request.args.get("activo"),
        tipo=request.args.get("tipo"),
        page=request.args.get("page"),
        page_size=current_app.config["PAGE_SIZE"],
    )
    return render_template("inventario/list.html", retorno=url_actual(), **resultado)


@bp.route("/<int:producto_id>/inicial", methods=["GET", "POST"])
def inicial(producto_id: int):
    producto = _producto_o_404(producto_id)
    if request.method == "GET" and not producto["puede_inicial"]:
        if producto["activo"] != 1:
            flash("Reactivá el producto antes de registrar el stock inicial.", "error")
        else:
            flash("Este producto ya tiene stock inicial.", "error")
        return _redirigir("inventario.movimientos", producto_id=producto_id)

    form = StockInicialForm()
    if form.validate_on_submit():
        try:
            inventario_service.registrar_stock_inicial(producto_id, _datos_cantidad(form))
            flash("Stock inicial registrado correctamente.", "ok")
            return _redirigir("inventario.movimientos", producto_id=producto_id)
        except InventarioError as error:
            _mostrar_errores(error)
    return render_template(
        "inventario/cantidad.html",
        form=form,
        producto=producto,
        titulo="Registrar stock inicial",
        nota="Ingresá la cantidad contada. Cero significa que no hay existencias.",
    )


@bp.route("/<int:producto_id>/reposicion", methods=["GET", "POST"])
def reposicion(producto_id: int):
    producto = _producto_o_404(producto_id)
    if request.method == "GET" and not producto["puede_reponer"]:
        if producto["activo"] != 1:
            flash("Reactivá el producto antes de registrar una reposición.", "error")
        else:
            flash("Primero registrá el stock inicial.", "error")
        return _redirigir("inventario.movimientos", producto_id=producto_id)

    form = ReposicionForm()
    if form.validate_on_submit():
        try:
            inventario_service.reponer(producto_id, _datos_cantidad(form))
            flash("Reposición registrada correctamente.", "ok")
            return _redirigir("inventario.movimientos", producto_id=producto_id)
        except InventarioError as error:
            _mostrar_errores(error)
    return render_template(
        "inventario/cantidad.html",
        form=form,
        producto=producto,
        titulo="Reponer stock",
        nota="La cantidad se suma al stock actual. No reemplaza el stock existente.",
    )


@bp.route("/<int:producto_id>/ajuste", methods=["GET", "POST"])
def ajuste(producto_id: int):
    producto = _producto_o_404(producto_id)
    if request.method == "GET" and not producto["puede_ajustar"]:
        flash("Primero registrá el stock inicial.", "error")
        return _redirigir("inventario.movimientos", producto_id=producto_id)

    form = AjusteForm()
    if form.validate_on_submit():
        try:
            inventario_service.ajustar(
                producto_id,
                {
                    "stock_real": form.stock_real.data,
                    "unidad_entrada": form.unidad_entrada.data,
                },
            )
            flash("Stock ajustado correctamente.", "ok")
            return _redirigir("inventario.movimientos", producto_id=producto_id)
        except InventarioError as error:
            _mostrar_errores(error)
    return render_template("inventario/ajuste.html", form=form, producto=producto)


@bp.route("/<int:producto_id>/descuento", methods=["GET", "POST"])
def descuento(producto_id: int):
    producto = _producto_o_404(producto_id)
    if request.method == "GET" and not producto["puede_descontar"]:
        flash("Primero registrá el stock inicial.", "error")
        return _redirigir("inventario.movimientos", producto_id=producto_id)

    form = DescuentoForm()
    if form.validate_on_submit():
        try:
            inventario_service.descontar(producto_id, _datos_cantidad(form) | {"motivo": form.motivo.data})
            flash("Descuento registrado correctamente.", "ok")
            return _redirigir("inventario.movimientos", producto_id=producto_id)
        except InventarioError as error:
            _mostrar_errores(error)
    return render_template("inventario/descuento.html", form=form, producto=producto)


@bp.get("/<int:producto_id>/movimientos")
def movimientos(producto_id: int):
    resultado = inventario_service.listar_movimientos(
        producto_id,
        page=request.args.get("page"),
        page_size=current_app.config["PAGE_SIZE"],
    )
    if resultado is None:
        abort(404)
    return render_template("inventario/movimientos.html", **resultado)
