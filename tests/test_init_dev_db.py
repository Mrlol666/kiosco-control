import hashlib
import sqlite3
from pathlib import Path

from app import create_app
from scripts.init_dev_db import inicializar


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _seed_minima(path: Path) -> None:
    conexion = sqlite3.connect(path)
    conexion.execute("CREATE TABLE productos (producto_id INTEGER PRIMARY KEY)")
    conexion.commit()
    conexion.close()


def _tablas(path: Path) -> set[str]:
    conexion = sqlite3.connect(path)
    try:
        filas = conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    finally:
        conexion.close()
    return {fila[0] for fila in filas}


def test_init_de_base_nueva_crea_tablas_del_carrito(tmp_path):
    seed = tmp_path / "seed.sqlite"
    dest = tmp_path / "dev.sqlite"
    _seed_minima(seed)
    huella = _sha256(seed)

    assert inicializar(seed, dest, force=False) == 0
    assert {"carritos", "carrito_lineas"} <= _tablas(dest)
    assert _sha256(seed) == huella


def test_init_sobre_base_existente_es_idempotente(tmp_path):
    seed = tmp_path / "seed.sqlite"
    dest = tmp_path / "dev.sqlite"
    _seed_minima(seed)
    inicializar(seed, dest, force=False)

    conexion = sqlite3.connect(dest)
    conexion.execute(
        """
        INSERT INTO carritos (estado, creado_en, pendiente_en)
        VALUES ('EN_CURSO', '2026-10-19 18:00:00', NULL)
        """
    )
    conexion.commit()
    conexion.close()
    huella = _sha256(seed)

    assert inicializar(seed, dest, force=False) == 0
    conexion = sqlite3.connect(dest)
    total = conexion.execute("SELECT COUNT(*) FROM carritos").fetchone()[0]
    conexion.close()
    assert total == 1
    assert _sha256(seed) == huella


def test_force_reconstruye_desde_seed_y_crea_carrito(tmp_path):
    seed = tmp_path / "seed.sqlite"
    dest = tmp_path / "dev.sqlite"
    _seed_minima(seed)
    huella = _sha256(seed)
    inicializar(seed, dest, force=False)

    conexion = sqlite3.connect(dest)
    conexion.execute(
        """
        INSERT INTO carritos (estado, creado_en, pendiente_en)
        VALUES ('EN_CURSO', '2026-10-19 18:00:00', NULL)
        """
    )
    conexion.commit()
    conexion.close()

    assert inicializar(seed, dest, force=True) == 0
    conexion = sqlite3.connect(dest)
    total = conexion.execute("SELECT COUNT(*) FROM carritos").fetchone()[0]
    tablas = {
        fila[0]
        for fila in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    conexion.close()
    assert total == 0
    assert {"carritos", "carrito_lineas", "productos"} <= tablas
    assert _sha256(seed) == huella


def test_la_aplicacion_asegura_el_carrito_una_vez_al_iniciar(tmp_path):
    destino = tmp_path / "operacional.sqlite"
    seed = tmp_path / "seed.sqlite"
    _seed_minima(destino)
    seed.write_bytes(destino.read_bytes())
    huella = _sha256(seed)
    create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-kiosco-control",
            "DATABASE_PATH": destino,
            "SEED_DATABASE_PATH": seed,
        }
    )
    assert {"carritos", "carrito_lineas"} <= _tablas(destino)
    assert _sha256(seed) == huella


def test_el_sql_de_v03_no_borra_tablas():
    sql = (
        Path(__file__).resolve().parents[1] / "scripts" / "sql" / "001_carrito.sql"
    ).read_text(encoding="utf-8")
    assert "DROP TABLE" not in sql.upper()
