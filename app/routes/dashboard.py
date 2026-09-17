from flask import Blueprint, render_template

from app.services import productos as productos_service

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    metricas = productos_service.obtener_metricas()
    return render_template("dashboard/index.html", metricas=metricas)
