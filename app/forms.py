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
