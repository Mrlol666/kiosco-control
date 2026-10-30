from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

from app.config import SQLITE_BUSY_TIMEOUT_MS


class SeedDatabaseError(RuntimeError):
    """Se intentó abrir la base seed como base operacional."""


def _as_path(value: Path | str) -> Path:
    return Path(value)


def _is_seed_path(db_path: Path, seed_path: Path) -> bool:
    try:
        resolved_db = db_path.resolve()
        resolved_seed = seed_path.resolve()
    except OSError:
        return False
    if resolved_db == resolved_seed:
        return True
    try:
        return db_path.exists() and seed_path.exists() and db_path.samefile(seed_path)
    except OSError:
        return False


def assert_operational_db(db_path: Path | str, seed_path: Path | str) -> Path:
    """Impide usar la seed como base operacional."""
    operational = _as_path(db_path)
    seed = _as_path(seed_path)
    if _is_seed_path(operational, seed):
        raise SeedDatabaseError(
            "La base seed es inmutable y no puede usarse como base operacional. "
            "Usá instance/kiosco_dev.sqlite (python scripts/init_dev_db.py)."
        )
    return operational


def get_db() -> sqlite3.Connection:
    if "db" in g:
        return g.db

    db_path = assert_operational_db(
        current_app.config["DATABASE_PATH"],
        current_app.config["SEED_DATABASE_PATH"],
    )
    if not db_path.exists():
        raise FileNotFoundError(
            f"No se encontró la base operacional: {db_path}. "
            "Ejecutá: python scripts/init_dev_db.py"
        )

    timeout_ms = int(
        current_app.config.get("SQLITE_BUSY_TIMEOUT_MS", SQLITE_BUSY_TIMEOUT_MS)
    )
    connection = sqlite3.connect(db_path, timeout=timeout_ms / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    g.db = connection
    return connection


def close_db(exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def ruta_sql_carrito() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "sql" / "001_carrito.sql"


def aplicar_estructura_v03(db_path: Path | str, seed_path: Path | str | None = None) -> None:
    """Crea las tablas del carrito si faltan. No borra datos ni toca la seed."""
    destino = _as_path(db_path)
    if seed_path is not None:
        assert_operational_db(destino, seed_path)
    if not destino.is_file():
        raise FileNotFoundError(f"No se encontró la base operacional: {destino}")

    sql = ruta_sql_carrito().read_text(encoding="utf-8")
    if "DROP TABLE" in sql.upper():
        raise RuntimeError("El SQL de v0.3 no puede borrar tablas.")

    conexion = sqlite3.connect(destino)
    try:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(sql)
    finally:
        conexion.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    destino = _as_path(app.config["DATABASE_PATH"])
    seed = app.config["SEED_DATABASE_PATH"]
    if not destino.is_file() or _is_seed_path(destino, seed):
        return
    aplicar_estructura_v03(destino, seed)


def begin_immediate() -> None:
    get_db().execute("BEGIN IMMEDIATE")


def commit_transaccion() -> None:
    get_db().commit()


def rollback_transaccion() -> None:
    conexion = get_db()
    if conexion.in_transaction:
        conexion.rollback()
