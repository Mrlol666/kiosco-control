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

    csrf.init_app(app)
    init_db(app)

    from app.routes.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)
    return app
