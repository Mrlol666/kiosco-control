PRAGMA foreign_keys = ON;


DROP TABLE IF EXISTS detalle_venta;
DROP TABLE IF EXISTS movimientos_stock;
DROP TABLE IF EXISTS gastos;
DROP TABLE IF EXISTS ventas;
DROP TABLE IF EXISTS medios_pago;
DROP TABLE IF EXISTS precios_minoristas;
DROP TABLE IF EXISTS precios_mayoristas;
DROP TABLE IF EXISTS sucursales_dia_merlo;
DROP TABLE IF EXISTS sucursales_mayoristas_cercanas;
DROP TABLE IF EXISTS metadata_fuentes;
DROP TABLE IF EXISTS productos;

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

CREATE TABLE precios_minoristas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_ean TEXT NOT NULL,
    id_sucursal TEXT NOT NULL,
    sucursal TEXT,
    calle TEXT,
    numero TEXT,
    barrio TEXT,
    localidad TEXT,
    precio_lista REAL,
    precio_referencia REAL,
    promo1_precio REAL,
    promo1_leyenda TEXT,
    promo2_precio REAL,
    promo2_leyenda TEXT,
    fecha_dato TEXT,
    FOREIGN KEY (codigo_ean) REFERENCES productos(codigo_ean)
);

CREATE TABLE precios_mayoristas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_ean TEXT NOT NULL,
    id_comercio TEXT,
    mayorista TEXT,
    id_sucursal TEXT,
    sucursal TEXT,
    localidad TEXT,
    provincia TEXT,
    dun14 TEXT,
    descripcion_mayorista TEXT,
    marca_mayorista TEXT,
    precio_unitario_con_iva REAL,
    precio_unitario_sin_iva REAL,
    unidad_venta REAL,
    precio_bulto_con_iva REAL,
    precio_bulto_sin_iva REAL,
    es_cercano_zona_oeste INTEGER NOT NULL DEFAULT 0 CHECK (es_cercano_zona_oeste IN (0,1)),
    fecha_dato TEXT,
    FOREIGN KEY (codigo_ean) REFERENCES productos(codigo_ean)
);

CREATE TABLE sucursales_dia_merlo (
    id_sucursal TEXT PRIMARY KEY,
    sucursal TEXT,
    tipo TEXT,
    calle TEXT,
    numero TEXT,
    barrio TEXT,
    localidad TEXT,
    provincia TEXT,
    latitud REAL,
    longitud REAL,
    usada_en_catalogo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE sucursales_mayoristas_cercanas (
    id_comercio TEXT,
    mayorista TEXT,
    id_sucursal TEXT,
    sucursal TEXT,
    calle TEXT,
    numero TEXT,
    barrio TEXT,
    localidad TEXT,
    provincia TEXT,
    latitud REAL,
    longitud REAL,
    PRIMARY KEY (id_comercio, id_sucursal)
);

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

CREATE TABLE gastos (
    gasto_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    categoria TEXT,
    concepto TEXT NOT NULL,
    importe REAL NOT NULL CHECK (importe >= 0),
    observaciones TEXT
);

CREATE TABLE metadata_fuentes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE INDEX idx_productos_descripcion ON productos(descripcion);
CREATE INDEX idx_productos_marca ON productos(marca);
CREATE INDEX idx_productos_activo ON productos(activo);
CREATE INDEX idx_minorista_ean ON precios_minoristas(codigo_ean);
CREATE INDEX idx_mayorista_ean ON precios_mayoristas(codigo_ean);
CREATE INDEX idx_mayorista_local ON precios_mayoristas(codigo_ean, es_cercano_zona_oeste);
CREATE INDEX idx_ventas_fecha ON ventas(fecha_hora);
CREATE INDEX idx_detalle_venta_id ON detalle_venta(venta_id);
CREATE INDEX idx_mov_stock_producto ON movimientos_stock(producto_id, fecha_hora);

CREATE VIEW vw_productos_margen AS
SELECT
    producto_id,
    codigo_ean,
    descripcion,
    marca,
    tipo_venta,
    precio_compra_actual,
    precio_venta_actual,
    CASE
      WHEN precio_compra_actual IS NOT NULL AND precio_venta_actual IS NOT NULL
      THEN ROUND(precio_venta_actual - precio_compra_actual, 2)
      ELSE NULL
    END AS margen_bruto_monto,
    CASE
      WHEN precio_compra_actual IS NOT NULL AND precio_venta_actual > 0
      THEN ROUND((precio_venta_actual - precio_compra_actual) / precio_venta_actual * 100.0, 2)
      ELSE NULL
    END AS margen_bruto_sobre_venta_pct,
    calidad_dato
FROM productos;

CREATE VIEW vw_stock_bajo AS
SELECT *
FROM productos
WHERE activo = 1
  AND stock_actual IS NOT NULL
  AND stock_minimo IS NOT NULL
  AND stock_actual <= stock_minimo;
