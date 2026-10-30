from __future__ import annotations

import sqlite3
from math import ceil

from app.db import begin_immediate, commit_transaccion, rollback_transaccion
from app.repositories import productos as productos_repo

TIPOS_VENTA = {"UNIDAD", "PESO"}
ESTADOS = {"activos", "inactivos", "todos"}
LIKE_ESCAPE = "!"
LARGOS_CODIGO_COMPLETO = {8, 12, 13}
CODIGO_INTERNO_INICIAL = "9990000000001"
CODIGO_INTERNO_MAXIMO = "9999999999999"

ETIQUETAS_CALIDAD = {
    "OK": "Correcto",
    "SIN_MATCH_MAYORISTA": "Sin referencia mayorista",
    "MAYORISTA_>=_MINORISTA": "Revisar precio mayorista",
    "REVISAR_PRECIO_VENTA_BAJO|SIN_MATCH_MAYORISTA": "Revisar precio de venta",
    "MANUAL": "Producto manual",
}

EXPLICACIONES_CALIDAD = {
    "OK": "Los datos de referencia no presentan alertas detectadas.",
    "SIN_MATCH_MAYORISTA": "No se encontró una coincidencia mayorista exacta para este producto.",
    "MAYORISTA_>=_MINORISTA": (
        "El precio mayorista de referencia encontrado es igual o superior al "
        "precio minorista. Verificá el costo antes de utilizarlo."
    ),
    "REVISAR_PRECIO_VENTA_BAJO|SIN_MATCH_MAYORISTA": (
        "El precio de venta de referencia presenta una posible anomalía y conviene verificarlo."
    ),
    "MANUAL": "Este producto fue agregado manualmente al catálogo.",
}


class ProductoError(Exception):
    def __init__(self, mensajes: str | list[str]):
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        self.mensajes = mensajes
        super().__init__(" ".join(mensajes))


def parece_ean_completo(consulta: str) -> bool:
    texto = consulta.strip()
    return texto.isdigit() and len(texto) in LARGOS_CODIGO_COMPLETO


def unidad_stock_para(tipo_venta: str) -> str:
    return "G" if tipo_venta == "PESO" else "UNIDAD"


def patron_like(consulta: str) -> str:
    escaped = (
        consulta.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


def normalizar_tipo(tipo: str | None) -> str:
    if not tipo:
        return "todos"
    valor = tipo.strip()
    if valor.lower() == "todos":
        return "todos"
    valor = valor.upper()
    return valor if valor in TIPOS_VENTA else "todos"


def normalizar_estado(estado: str | None) -> str:
    if not estado:
        return "activos"
    valor = estado.strip().lower()
    return valor if valor in ESTADOS else "activos"


def normalizar_pagina(page: str | int | None) -> int:
    try:
        numero = int(page)
    except (TypeError, ValueError):
        return 1
    return numero if numero >= 1 else 1


def _activo_sql(estado: str) -> int | None:
    if estado == "activos":
        return 1
    if estado == "inactivos":
        return 0
    return None


def _tipo_sql(tipo: str) -> str | None:
    return tipo if tipo in TIPOS_VENTA else None


def format_precio(valor) -> str:
    if valor is None:
        return "Sin configurar"
    numero = round(float(valor), 2)
    entero, frac = f"{numero:.2f}".split(".")
    grupos = []
    while entero:
        grupos.append(entero[-3:])
        entero = entero[:-3]
    entero_fmt = ".".join(reversed(grupos))
    if frac == "00":
        return f"${entero_fmt}"
    return f"${entero_fmt},{frac}"


def format_precio_con_unidad(valor, tipo_venta: str | None, *, vacio: str = "Sin configurar") -> str:
    if valor is None:
        return vacio
    texto = format_precio(valor)
    if tipo_venta == "PESO":
        return f"{texto} / kg"
    return texto


def format_tipo_venta(tipo_venta: str | None) -> str:
    if tipo_venta == "PESO":
        return "Por peso"
    if tipo_venta == "UNIDAD":
        return "Por unidad"
    return tipo_venta or "—"


def format_unidad_stock(unidad_stock: str | None) -> str:
    if unidad_stock == "G":
        return "Gramos"
    if unidad_stock == "UNIDAD":
        return "Unidades"
    return unidad_stock or "—"


def format_alcance(valor: str | None) -> str:
    if valor is None or str(valor).strip() == "":
        return "—"
    if valor == "LOCAL":
        return "Local"
    if valor == "NACIONAL":
        return "Nacional"
    return str(valor)


def presentar_calidad(valor: str | None) -> dict:
    if valor is None or str(valor).strip() == "":
        return {"etiqueta": "—", "explicacion": None}
    codigo = str(valor)
    if codigo in ETIQUETAS_CALIDAD:
        return {
            "etiqueta": ETIQUETAS_CALIDAD[codigo],
            "explicacion": EXPLICACIONES_CALIDAD.get(codigo),
        }
    amigable = codigo.replace("|", " · ").replace("_", " ")
    return {"etiqueta": amigable, "explicacion": None}


def format_gramos(valor) -> str:
    gramos = float(valor)
    if gramos >= 1000:
        kilos = gramos / 1000.0
        if abs(kilos - round(kilos)) < 1e-9:
            return f"{int(round(kilos))} kg"
        texto = f"{kilos:.3f}".rstrip("0").rstrip(".")
        return f"{texto.replace('.', ',')} kg"
    if gramos.is_integer():
        return f"{int(gramos)} g"
    return f"{str(gramos).replace('.', ',')} g"


def format_cantidad(valor, tipo_venta: str | None) -> str:
    if tipo_venta == "PESO":
        return format_gramos(valor)
    numero = int(valor) if float(valor).is_integer() else valor
    if numero == 1:
        return "1 unidad"
    return f"{numero} unidades"


def format_stock(valor, tipo_venta: str | None, *, es_stock_actual: bool = True) -> str:
    if valor is None:
        return "Sin stock inicial" if es_stock_actual else "Sin mínimo cargado"
    return format_cantidad(valor, tipo_venta)


def _es_codigo_interno(codigo: str, origen: str | None) -> bool:
    return (
        origen == "MANUAL"
        and isinstance(codigo, str)
        and len(codigo) == 13
        and codigo.startswith("999")
        and codigo.isdigit()
    )


def _presentar_listado(fila: dict) -> dict:
    item = dict(fila)
    item["codigo_ean"] = str(item["codigo_ean"])
    tipo = item.get("tipo_venta")
    item["precio_venta_mostrar"] = format_precio_con_unidad(
        item.get("precio_venta_actual"), tipo
    )
    item["tipo_venta_mostrar"] = format_tipo_venta(tipo)
    item["unidad_stock_mostrar"] = format_unidad_stock(item.get("unidad_stock"))
    item["stock_mostrar"] = format_stock(
        item.get("stock_actual"), tipo, es_stock_actual=True
    )
    calidad = presentar_calidad(item.get("calidad_dato"))
    item["calidad_etiqueta"] = calidad["etiqueta"]
    item["calidad_explicacion"] = calidad["explicacion"]
    item["codigo_interno"] = _es_codigo_interno(
        item["codigo_ean"], item.get("origen_catalogo")
    )
    return item


def _texto_sepa(valor) -> str:
    if valor is None or valor == "":
        return "—"
    return str(valor)


def _presentar_detalle(fila: dict) -> dict:
    item = _presentar_listado(fila)
    tipo = item.get("tipo_venta")
    item["precio_compra_mostrar"] = format_precio_con_unidad(
        item.get("precio_compra_actual"), tipo
    )
    item["stock_minimo_mostrar"] = format_stock(
        item.get("stock_minimo"), tipo, es_stock_actual=False
    )
    item["precio_dia_28_mostrar"] = format_precio_con_unidad(
        item.get("precio_venta_dia_28"), tipo, vacio="—"
    )
    item["precio_dia_64_mostrar"] = format_precio_con_unidad(
        item.get("precio_venta_dia_64"), tipo, vacio="—"
    )
    item["precio_compra_referencia_mostrar"] = format_precio_con_unidad(
        item.get("precio_compra_referencia"), tipo, vacio="—"
    )
    item["mayorista_referencia"] = _texto_sepa(item.get("mayorista_referencia"))
    item["alcance_precio_compra"] = format_alcance(item.get("alcance_precio_compra"))
    return item


def listar(q=None, tipo=None, estado=None, page=None, page_size=50) -> dict:
    consulta = (q or "").strip()
    tipo_norm = normalizar_tipo(tipo)
    estado_norm = normalizar_estado(estado)
    pagina = normalizar_pagina(page)
    tamanio = int(page_size) if int(page_size) > 0 else 50

    ean_exacto = None
    like_pattern = None
    if consulta:
        if parece_ean_completo(consulta):
            ean_exacto = consulta
        else:
            like_pattern = patron_like(consulta)

    filtros = {
        "tipo_venta": _tipo_sql(tipo_norm),
        "activo": _activo_sql(estado_norm),
        "ean_exacto": ean_exacto,
        "like_pattern": like_pattern,
        "q": consulta,
    }

    total = productos_repo.contar(
        tipo_venta=filtros["tipo_venta"],
        activo=filtros["activo"],
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
    )
    offset = (pagina - 1) * tamanio
    filas = productos_repo.listar(
        tipo_venta=filtros["tipo_venta"],
        activo=filtros["activo"],
        ean_exacto=ean_exacto,
        like_pattern=like_pattern,
        limit=tamanio,
        offset=offset,
    )
    total_paginas = ceil(total / tamanio) if total else 0

    return {
        "items": [_presentar_listado(fila) for fila in filas],
        "total": total,
        "page": pagina,
        "page_size": tamanio,
        "total_pages": total_paginas,
        "q": consulta,
        "tipo": tipo_norm,
        "estado": estado_norm,
    }


def obtener(producto_id: int) -> dict | None:
    fila = productos_repo.obtener_por_id(producto_id)
    if fila is None:
        return None
    return _presentar_detalle(fila)


def obtener_metricas() -> dict:
    return productos_repo.obtener_metricas()


def _texto_opcional(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _parsear_no_negativo(valor, nombre: str, obligatorio: bool = False):
    if valor is None:
        texto = ""
    else:
        texto = str(valor).strip().replace(" ", "")
    if texto == "":
        if obligatorio:
            return None, f"{nombre} es obligatorio."
        return None, None
    if texto.count(",") == 1 and "." not in texto:
        texto = texto.replace(",", ".")
    try:
        numero = float(texto)
    except ValueError:
        return None, f"{nombre} no es un número válido."
    if numero < 0:
        if "precio" in nombre.lower():
            return None, "El precio no puede ser negativo."
        return None, f"{nombre} no puede ser negativo."
    return numero, None


def _incrementar_codigo(codigo: str) -> str:
    caracteres = list(codigo)
    indice = len(caracteres) - 1
    while indice >= 0:
        digito = ord(caracteres[indice]) - 48
        if digito < 9:
            caracteres[indice] = chr(48 + digito + 1)
            return "".join(caracteres)
        caracteres[indice] = "0"
        indice -= 1
    raise ProductoError("No hay más códigos internos disponibles.")


def generar_codigo_interno() -> str:
    ultimo = productos_repo.max_codigo_interno()
    candidato = CODIGO_INTERNO_INICIAL if ultimo is None else _incrementar_codigo(ultimo)
    while productos_repo.existe_codigo(candidato):
        if candidato >= CODIGO_INTERNO_MAXIMO:
            raise ProductoError("No hay más códigos internos disponibles.")
        candidato = _incrementar_codigo(candidato)
    return candidato


def _validar_codigo_ingresado(codigo: str) -> str | None:
    if not codigo.isdigit() or len(codigo) not in LARGOS_CODIGO_COMPLETO:
        return "El código debe tener 8, 12 o 13 dígitos numéricos. Conservá los ceros."
    return None


def _validar_campos_comunes(datos: dict) -> tuple[dict, list[str]]:
    errores: list[str] = []
    descripcion = _texto_opcional(datos.get("descripcion"))
    if not descripcion:
        errores.append("La descripción es obligatoria.")

    tipo = _texto_opcional(datos.get("tipo_venta"))
    if tipo:
        tipo = tipo.upper()
    if tipo not in TIPOS_VENTA:
        errores.append("La forma de venta debe ser por unidad o por peso.")
        tipo = None

    precio_venta, error_venta = _parsear_no_negativo(
        datos.get("precio_venta_actual"), "El precio de venta", obligatorio=True
    )
    if error_venta:
        errores.append(error_venta)

    precio_compra, error_compra = _parsear_no_negativo(
        datos.get("precio_compra_actual"), "El precio de compra"
    )
    if error_compra:
        errores.append(error_compra)

    stock_minimo, error_stock = _parsear_no_negativo(
        datos.get("stock_minimo"), "El stock mínimo"
    )
    if error_stock:
        errores.append(error_stock)

    normalizado = {
        "descripcion": descripcion,
        "marca": _texto_opcional(datos.get("marca")),
        "categoria": _texto_opcional(datos.get("categoria")),
        "tipo_venta": tipo,
        "unidad_stock": unidad_stock_para(tipo) if tipo else None,
        "precio_venta_actual": precio_venta,
        "precio_compra_actual": precio_compra,
        "stock_minimo": stock_minimo,
    }
    return normalizado, errores


def crear(datos: dict) -> int:
    normalizado, errores = _validar_campos_comunes(datos)
    codigo = _texto_opcional(datos.get("codigo_ean"))
    if codigo:
        error_codigo = _validar_codigo_ingresado(codigo)
        if error_codigo:
            errores.append(error_codigo)
        elif productos_repo.existe_codigo(codigo):
            errores.append("Ya existe un producto con ese código.")
    if errores:
        raise ProductoError(errores)

    if codigo is None:
        codigo = generar_codigo_interno()
    elif productos_repo.existe_codigo(codigo):
        raise ProductoError("Ya existe un producto con ese código.")

    payload = {
        **normalizado,
        "codigo_ean": codigo,
        "precio_venta_confirmado": 1,
        "precio_compra_confirmado": 1 if normalizado["precio_compra_actual"] is not None else 0,
    }
    try:
        return productos_repo.insertar(payload)
    except sqlite3.IntegrityError:
        raise ProductoError("Ya existe un producto con ese código.") from None


def _valores_distintos(actual, nuevo) -> bool:
    if actual is None and nuevo is None:
        return False
    if actual is None or nuevo is None:
        return True
    return float(actual) != float(nuevo)


def editar(producto_id: int, datos: dict) -> None:
    actual = productos_repo.obtener_por_id(producto_id)
    if actual is None:
        raise ProductoError("El producto no existe.")

    normalizado, errores = _validar_campos_comunes(datos)
    if errores:
        raise ProductoError(errores)

    tipo_nuevo = normalizado["tipo_venta"]
    if tipo_nuevo != actual["tipo_venta"]:
        historial = productos_repo.contar_historial(producto_id)
        if historial["total"] > 0:
            raise ProductoError(
                "No se puede cambiar la forma de venta porque este producto ya tiene "
                "movimientos registrados."
            )

    venta_confirmado = actual["precio_venta_confirmado"]
    if _valores_distintos(actual["precio_venta_actual"], normalizado["precio_venta_actual"]):
        venta_confirmado = 1

    compra_confirmado = actual["precio_compra_confirmado"]
    if _valores_distintos(actual["precio_compra_actual"], normalizado["precio_compra_actual"]):
        compra_confirmado = 1 if normalizado["precio_compra_actual"] is not None else 0

    payload = {
        **normalizado,
        "precio_venta_confirmado": venta_confirmado,
        "precio_compra_confirmado": compra_confirmado,
    }
    try:
        productos_repo.actualizar(producto_id, payload)
    except sqlite3.IntegrityError:
        raise ProductoError("No se pudo guardar el producto.") from None


def actualizar_precio_venta(producto_id: int, precio) -> None:
    if productos_repo.obtener_por_id(producto_id) is None:
        raise ProductoError("El producto no existe.")
    valor, error = _parsear_no_negativo(precio, "El precio de venta", obligatorio=True)
    if error:
        raise ProductoError(error)
    begin_immediate()
    try:
        productos_repo.actualizar_solo_precio_venta(producto_id, valor)
        commit_transaccion()
    except ProductoError:
        rollback_transaccion()
        raise
    except Exception:
        rollback_transaccion()
        raise ProductoError("No se pudo actualizar el precio de venta.") from None


def desactivar(producto_id: int) -> None:
    if productos_repo.obtener_por_id(producto_id) is None:
        raise ProductoError("El producto no existe.")
    productos_repo.actualizar_activo(producto_id, 0)


def reactivar(producto_id: int) -> None:
    if productos_repo.obtener_por_id(producto_id) is None:
        raise ProductoError("El producto no existe.")
    productos_repo.actualizar_activo(producto_id, 1)
