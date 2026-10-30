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

Kiosco Control se encuentra actualmente en desarrollo.

- **Última versión estable:** `v0.2` — Inventario completado.
- **Versión en revisión:** `v0.3` — Carrito de ventas.

La funcionalidad inicial del carrito ya fue implementada, pero todavía se encuentra en etapa de pruebas y correcciones antes de considerarla una versión estable.

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

`v0.1`

### v0.2 — Inventario completada

La versión v0.2 está marcada en Git con:

`v0.2`

Incluye:

- listado operativo de inventario;
- búsqueda y filtros;
- stock inicial;
- reposiciones;
- ajuste por conteo;
- descuento de stock;
- productos por unidad;
- productos por peso en gramos/kg;
- historial de movimientos;
- conservación de filtros y de la navegación al volver a un listado;
- distinción entre stock sin inicializar, sin existencias y stock bajo;
- transacciones atómicas;
- trazabilidad de cada cambio de stock.


### v0.3 — Carrito de ventas en revisión

La funcionalidad inicial del carrito ya está implementada, pero aún se encuentra en etapa de revisión y correcciones.

Esta versión busca permitir armar una venta de forma sencilla sin modificar el stock mientras se construye el carrito. La confirmación definitiva de la venta y el descuento transaccional del inventario corresponden a la siguiente etapa del proyecto.

**Importante:** `v0.3` todavía no está etiquetada como versión estable.

## Productos e Inventario

Productos administra el catálogo y los datos maestros: descripción, precios, forma de venta y stock mínimo.

Inventario administra las existencias: stock inicial, reposiciones, ajustes por conteo, descuentos e historial.

`stock_actual` no se edita directamente desde Productos. Solo cambia mediante una operación de inventario, y cada cambio queda registrado.

## Roadmap

- v0.1 — completada
- v0.2 — completada
- v0.3 — Carrito de ventas — en revisión
- v0.4 — Confirmación de ventas + descuento transaccional de stock
- v0.5 — Ventas por peso
- v0.6 — Historial y anulación
- v0.7 — Gastos y medios de pago
- v0.8 — Dashboard analítico y PDF
- v0.9 — estabilización
- v1.0 — versión final

## Estado de desarrollo

El repositorio se publica durante el desarrollo para conservar el historial del proyecto y mostrar su evolución. Las versiones etiquetadas en Git representan hitos estables; las funcionalidades que todavía están en revisión se mantienen sin tag de versión.

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

Desde la raíz del proyecto, con el entorno virtual activado:

python -m pytest tests -v
