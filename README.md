# Kiosco Control

Sistema web de gestión para kioscos, almacenes y pequeños comercios.

La aplicación busca facilitar la administración de productos, inventario, ventas y reportes mediante una interfaz sencilla para usuarios sin conocimientos técnicos.

## Tecnologías

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- pytest

## Estado actual

### v0.1 — completada

Incluye:

- infraestructura Flask;
- base SQLite independiente de desarrollo;
- catálogo inicial de 4313 productos;
- datos de referencia SEPA minoristas y mayoristas;
- listado de productos;
- búsqueda por descripción, marca y código;
- filtros;
- productos por unidad y por peso;
- detalle de producto;
- creación de productos;
- edición;
- desactivación y reactivación;
- códigos internos;
- validaciones;
- protección CSRF;
- dashboard básico;
- interfaz inicial responsive;
- tests automáticos.

La versión v0.1 está marcada en Git con:

v0.1

## Versión en desarrollo

### v0.2 — Inventario

Objetivos:

- registrar stock inicial;
- reponer mercadería;
- ajustar stock;
- registrar todos los movimientos;
- soportar unidades y productos por peso;
- historial de inventario;
- métricas de stock.

## Próximas versiones

- v0.3 — Carrito
- v0.4 — Confirmación de ventas
- v0.5 — Ventas por peso
- v0.6 — Historial y anulación
- v0.7 — Gastos y medios de pago
- v0.8 — Dashboard analítico y reportes PDF
- v0.9 — estabilización y pruebas finales
- v1.0 — versión final

## Base de datos

La base original se encuentra en:

data/seed/kiosco_merlo_sepa.sqlite

y no debe modificarse.

La aplicación trabaja con:

instance/kiosco_dev.sqlite

Para recrear la base de desarrollo:

python scripts/init_dev_db.py --force

## Ejecutar el proyecto

Activar el entorno virtual:

.\.venv\Scripts\Activate.ps1

Ejecutar:

python run.py

Abrir:

http://127.0.0.1:5000

## Tests

Ejecutar:

python -m pytest tests -v