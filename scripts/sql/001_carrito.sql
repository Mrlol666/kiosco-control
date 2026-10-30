CREATE TABLE IF NOT EXISTS carritos (
    carrito_id INTEGER PRIMARY KEY AUTOINCREMENT,
    estado TEXT NOT NULL CHECK (estado IN ('EN_CURSO', 'PENDIENTE')),
    creado_en TEXT NOT NULL,
    pendiente_en TEXT,
    etiqueta TEXT,
    CHECK (
        (estado = 'EN_CURSO' AND pendiente_en IS NULL)
        OR (estado = 'PENDIENTE' AND pendiente_en IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS carrito_lineas (
    carrito_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad REAL NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (carrito_id, producto_id),
    FOREIGN KEY (carrito_id) REFERENCES carritos(carrito_id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(producto_id)
);

CREATE INDEX IF NOT EXISTS idx_carritos_estado_pendiente
    ON carritos (estado, pendiente_en);
