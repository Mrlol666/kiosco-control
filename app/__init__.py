from flask import Flask
from flask_wtf import CSRFProtect

from app.config import Config
from app.db import init_app as init_db

csrf = CSRFProtect()


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    app.url_map.strict_slashes = False

    csrf.init_app(app)
    init_db(app)

    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.inventario import bp as inventario_bp
    from app.routes.productos import bp as productos_bp
    from app.routes.venta import bp as venta_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(venta_bp)

    from app.navegacion import registrar_plantillas

    registrar_plantillas(app)
    return app
