from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField


class ProductoNuevoForm(FlaskForm):
    codigo_ean = StringField("Código / EAN")
    descripcion = StringField("Descripción")
    marca = StringField("Marca")
    categoria = StringField("Categoría")
    tipo_venta = SelectField(
        "Forma de venta",
        choices=[
            ("", "Elegí una forma de venta"),
            ("UNIDAD", "Por unidad"),
            ("PESO", "Por peso"),
        ],
        validate_choice=False,
    )
    precio_venta_actual = StringField("Precio de venta")
    precio_compra_actual = StringField("Precio de compra")
    stock_minimo = StringField("Stock mínimo")
    submit = SubmitField("Guardar")


class ProductoEditarForm(FlaskForm):
    descripcion = StringField("Descripción")
    marca = StringField("Marca")
    categoria = StringField("Categoría")
    tipo_venta = SelectField(
        "Forma de venta",
        choices=[("UNIDAD", "Por unidad"), ("PESO", "Por peso")],
        validate_choice=False,
    )
    precio_venta_actual = StringField("Precio de venta")
    precio_compra_actual = StringField("Precio de compra")
    stock_minimo = StringField("Stock mínimo")
    submit = SubmitField("Guardar cambios")


class AccionProductoForm(FlaskForm):
    submit = SubmitField("Confirmar")


class StockInicialForm(FlaskForm):
    cantidad = StringField("Cantidad")
    unidad_entrada = SelectField(
        "Unidad",
        choices=[("G", "Gramos"), ("KG", "Kilogramos")],
        default="G",
        validate_choice=False,
    )
    submit = SubmitField("Registrar stock inicial")


class ReposicionForm(FlaskForm):
    cantidad = StringField("Cantidad")
    unidad_entrada = SelectField(
        "Unidad",
        choices=[("G", "Gramos"), ("KG", "Kilogramos")],
        default="G",
        validate_choice=False,
    )
    submit = SubmitField("Registrar reposición")


class AjusteForm(FlaskForm):
    stock_real = StringField("Stock real contado")
    unidad_entrada = SelectField(
        "Unidad",
        choices=[("G", "Gramos"), ("KG", "Kilogramos")],
        default="G",
        validate_choice=False,
    )
    submit = SubmitField("Guardar ajuste")


class DescuentoForm(FlaskForm):
    cantidad = StringField("Cantidad a descontar")
    unidad_entrada = SelectField(
        "Unidad",
        choices=[("G", "Gramos"), ("KG", "Kilogramos")],
        default="G",
        validate_choice=False,
    )
    motivo = SelectField(
        "Motivo",
        choices=[
            ("", "Elegí un motivo"),
            ("ROTURA", "Rotura"),
            ("VENCIMIENTO", "Vencimiento"),
            ("MERMA", "Merma"),
            ("CONSUMO_INTERNO", "Consumo interno"),
            ("OTRO", "Otro"),
        ],
        validate_choice=False,
    )
    submit = SubmitField("Registrar descuento")
