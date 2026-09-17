from __future__ import annotations

import sqlite3
from pathlib import Path

CREATE_PRODUCTOS = """
CREATE TABLE productos (
    producto_id INTEGER PRIMARY KEY,
    codigo_ean TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    marca TEXT,
    categoria TEXT,
    cantidad_presentacion REAL,
    unidad_presentacion TEXT,
    unidad_presentacion_norm TEXT,
    cantidad_referencia REAL,
    unidad_referencia TEXT,
    unidad_referencia_norm TEXT,
    tipo_venta TEXT NOT NULL CHECK (tipo_venta IN ('UNIDAD','PESO')),
    unidad_stock TEXT NOT NULL CHECK (unidad_stock IN ('UNIDAD','G')),
    precio_venta_actual REAL,
    precio_venta_confirmado INTEGER NOT NULL DEFAULT 0 CHECK (precio_venta_confirmado IN (0,1)),
    precio_venta_dia_28 REAL,
    precio_venta_dia_64 REAL,
    precio_venta_ref_min REAL,
    precio_venta_ref_max REAL,
    precio_venta_ref_promedio REAL,
    precio_referencia_dia REAL,
    precio_compra_actual REAL,
    precio_compra_confirmado INTEGER NOT NULL DEFAULT 0 CHECK (precio_compra_confirmado IN (0,1)),
    precio_compra_referencia REAL,
    alcance_precio_compra TEXT,
    mayorista_referencia TEXT,
    mayorista_sucursal_referencia TEXT,
    mayorista_localidad_referencia TEXT,
    unidad_venta_mayorista REAL,
    precio_bulto_mayorista REAL,
    stock_actual REAL,
    stock_minimo REAL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)),
    origen_catalogo TEXT,
    fecha_minorista TEXT,
    fecha_mayorista TEXT,
    calidad_dato TEXT
);
"""

CREATE_OPERATIVAS = """
CREATE TABLE medios_pago (
    medio_pago_id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE ventas (
    venta_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora TEXT NOT NULL,
    medio_pago_id INTEGER NOT NULL,
    total REAL NOT NULL CHECK (total >= 0),
    estado TEXT NOT NULL DEFAULT 'CONFIRMADA' CHECK (estado IN ('CONFIRMADA','ANULADA')),
    observaciones TEXT,
    FOREIGN KEY (medio_pago_id) REFERENCES medios_pago(medio_pago_id)
);

CREATE TABLE detalle_venta (
    detalle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad REAL NOT NULL CHECK (cantidad > 0),
    unidad_cantidad TEXT NOT NULL CHECK (unidad_cantidad IN ('UNIDAD','G')),
    precio_venta_unitario REAL NOT NULL CHECK (precio_venta_unitario >= 0),
    costo_unitario REAL,
    subtotal REAL NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (venta_id) REFERENCES ventas(venta_id),
    FOREIGN KEY (producto_id) REFERENCES productos(producto_id)
);

CREATE TABLE movimientos_stock (
    movimiento_id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER NOT NULL,
    fecha_hora TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('ENTRADA','VENTA','AJUSTE','ANULACION')),
    cantidad REAL NOT NULL,
    unidad TEXT NOT NULL CHECK (unidad IN ('UNIDAD','G')),
    motivo TEXT,
    venta_id INTEGER,
    FOREIGN KEY (producto_id) REFERENCES productos(producto_id),
    FOREIGN KEY (venta_id) REFERENCES ventas(venta_id)
);
"""

INSERT_SQL = """
INSERT INTO productos (
    producto_id, codigo_ean, descripcion, marca, tipo_venta, unidad_stock,
    precio_venta_actual, precio_compra_actual, stock_actual, stock_minimo,
    activo, precio_venta_dia_28, precio_venta_dia_64, precio_compra_referencia,
    mayorista_referencia, alcance_precio_compra, fecha_minorista, fecha_mayorista,
    calidad_dato
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

PRODUCTOS_PRUEBA = [
    (
        1,
        "0000002674407",
        "PRESERVATIVOS",
        "PRIME",
        "UNIDAD",
        "UNIDAD",
        5830,
        None,
        None,
        None,
        1,
        5800,
        5830,
        None,
        None,
        None,
        "2026-09-11",
        None,
        "SIN_MATCH_MAYORISTA",
    ),
    (
        2,
        "7791234567890",
        "COCA COLA 2.25L",
        "COCA",
        "UNIDAD",
        "UNIDAD",
        2500,
        1800,
        10,
        5,
        1,
        2480,
        2500,
        1800,
        "MAXICONSUMO",
        "LOCAL",
        "2026-09-11",
        "2026-09-13",
        "OK",
    ),
    (
        3,
        "2403866000005",
        "QUESO CREMOSO",
        "SILVI",
        "PESO",
        "G",
        16690,
        12000,
        None,
        None,
        1,
        16500,
        16690,
        12000,
        "NINI",
        "LOCAL",
        "2026-09-11",
        "2026-09-13",
        "OK",
    ),
    (
        4,
        "7790000000002",
        "GALLETA INACTIVA",
        "RICO",
        "UNIDAD",
        "UNIDAD",
        900,
        None,
        None,
        None,
        0,
        900,
        900,
        None,
        None,
        None,
        "2026-09-11",
        None,
        "OK",
    ),
    (
        5,
        "2401111000008",
        "PAN DE MIGA",
        None,
        "PESO",
        "G",
        70,
        None,
        100,
        500,
        1,
        70,
        70,
        None,
        None,
        None,
        "2026-09-11",
        None,
        "REVISAR_PRECIO_VENTA_BAJO|SIN_MATCH_MAYORISTA",
    ),
    (
        6,
        "7790000000003",
        "AGUA MINERAL",
        "VILLAVICENCIO",
        "UNIDAD",
        "UNIDAD",
        800,
        500,
        None,
        None,
        1,
        790,
        800,
        500,
        "YAGUAR",
        "LOCAL",
        "2026-09-11",
        "2026-09-13",
        "OK",
    ),
]


def crear_base_de_prueba(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(CREATE_PRODUCTOS)
        connection.executescript(CREATE_OPERATIVAS)
        connection.executemany(INSERT_SQL, PRODUCTOS_PRUEBA)
        connection.commit()
    finally:
        connection.close()
