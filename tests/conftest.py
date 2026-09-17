from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app import create_app
from app.config import SEED_DB_PATH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="session")
def seed_sha256() -> str:
    return _sha256(SEED_DB_PATH)


@pytest.fixture(scope="session")
def hash_file():
    return _sha256


@pytest.fixture()
def app(tmp_path, seed_sha256):
    db_path = tmp_path / "kiosco_test.sqlite"
    db_path.touch()
    application = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-kiosco-control",
            "DATABASE_PATH": db_path,
        }
    )
    yield application
    assert _sha256(SEED_DB_PATH) == seed_sha256


@pytest.fixture()
def client(app):
    return app.test_client()
