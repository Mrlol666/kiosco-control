from pathlib import Path

import pytest

from app import create_app
from app.config import SEED_DB_PATH
from app.db import SeedDatabaseError, get_db


def test_create_app_works(app):
    assert app is not None
    assert app.testing is True


def test_dashboard_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Kiosco Control" in response.get_data(as_text=True)


def test_testing_db_does_not_point_to_seed(app):
    database_path = Path(app.config["DATABASE_PATH"])
    assert database_path.resolve() != SEED_DB_PATH.resolve()


def test_foreign_keys_are_enabled(app):
    with app.app_context():
        db = get_db()
        enabled = db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert enabled == 1


def test_seed_is_not_modified(hash_file, seed_sha256):
    assert hash_file(SEED_DB_PATH) == seed_sha256


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "docs" / "schema_kiosco.sql"
SCHEMA_SHA256 = "639d74766d6b98145f5b72abfdd95a3d2e3ab113d8f2ed7b096c6944e6eee3ce"


def test_schema_is_not_modified(hash_file):
    assert hash_file(SCHEMA_PATH) == SCHEMA_SHA256


def test_get_db_rejects_seed_as_operational():
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-kiosco-control",
            "DATABASE_PATH": SEED_DB_PATH,
        }
    )
    with application.app_context():
        with pytest.raises(SeedDatabaseError):
            get_db()
