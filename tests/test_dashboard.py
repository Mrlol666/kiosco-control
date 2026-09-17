import re


def _valor_metrica(html: str, etiqueta: str) -> str:
    patron = (
        r'class="metrics-value">([^<]+)</span>\s*'
        rf'<span class="metrics-label">{re.escape(etiqueta)}</span>'
    )
    match = re.search(patron, html)
    assert match, f"No se encontró la métrica {etiqueta}"
    return match.group(1).strip()


def test_dashboard_metricas_desde_sqlite(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert _valor_metrica(html, "Productos activos") == "5"
    assert _valor_metrica(html, "Productos inactivos") == "1"
    assert _valor_metrica(html, "Productos por unidad") == "3"
    assert _valor_metrica(html, "Productos por peso") == "2"
    assert int(_valor_metrica(html, "Productos activos")) == (
        int(_valor_metrica(html, "Productos por unidad"))
        + int(_valor_metrica(html, "Productos por peso"))
    )
    assert _valor_metrica(html, "Sin stock inicial") == "4"
    assert _valor_metrica(html, "Con stock bajo") == "1"
