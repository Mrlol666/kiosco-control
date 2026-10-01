from __future__ import annotations

from urllib.parse import unquote, urlsplit

_PREFIJOS = ("/inventario", "/productos")


def normalizar_destino(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if texto == "" or not _es_destino_interno(texto):
        return None
    return texto


def destino_o_fallback(valor, fallback: str) -> str:
    return normalizar_destino(valor) or fallback


def url_actual() -> str:
    from flask import request

    consulta = request.query_string.decode("utf-8")
    if consulta:
        return f"{request.path}?{consulta}"
    return request.path


def url_con_next(endpoint: str, **valores) -> str:
    from flask import request, url_for

    destino = normalizar_destino(request.values.get("next"))
    if destino is not None:
        valores["next"] = destino
    return url_for(endpoint, **valores)


def registrar_plantillas(app) -> None:
    @app.context_processor
    def _contexto_navegacion():
        from flask import request

        return {"next_retorno": normalizar_destino(request.values.get("next"))}

    @app.template_global("con_next")
    def con_next(endpoint: str, **valores):
        from flask import request, url_for

        destino = normalizar_destino(request.values.get("next"))
        if destino is not None:
            valores["next"] = destino
        return url_for(endpoint, **valores)


def _es_destino_interno(texto: str) -> bool:
    if not texto.startswith("/") or texto.startswith("//"):
        return False
    if any(ord(caracter) < 32 for caracter in texto):
        return False
    decodificado = _decodificar(texto)
    return _camino_interno(texto) and _camino_interno(decodificado)


def _decodificar(texto: str) -> str:
    actual = texto
    for _ in range(5):
        siguiente = unquote(actual)
        if siguiente == actual:
            return actual
        actual = siguiente
    return actual


def _camino_interno(texto: str) -> bool:
    if "\\" in texto or "://" in texto or texto.startswith("//"):
        return False
    if any(ord(caracter) < 32 for caracter in texto):
        return False
    partes = urlsplit(texto)
    if partes.scheme or partes.netloc:
        return False
    ruta = partes.path
    if not ruta.startswith("/") or ruta.startswith("//") or "\\" in ruta:
        return False
    if ruta == "/":
        return True
    for prefijo in _PREFIJOS:
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return True
    return False
