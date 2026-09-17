# Kiosco Control — Reglas obligatorias del proyecto

## Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Aplicación web responsive para PC/notebook y celular.

## Base de datos

La base original:

data/seed/kiosco_merlo_sepa.sqlite

es INMUTABLE.

Nunca debe ser modificada, actualizada ni utilizada como base operacional.

La aplicación debe trabajar con:

instance/kiosco_dev.sqlite

creada como copia de la seed.

Nunca ejecutar:

docs/schema_kiosco.sql

contra la base seed ni contra una base que contenga datos que deban conservarse.

Cada conexión SQLite debe ejecutar:

PRAGMA foreign_keys = ON

`codigo_ean` siempre debe manejarse como TEXT.

Nunca convertir `codigo_ean` a INTEGER.

## Arquitectura

Mantener separación:

Route
→ Service
→ Repository
→ SQLite

Las rutas HTTP no deben contener SQL.

Los repositories contienen acceso a datos.

Los services contienen validaciones y reglas de negocio.

Los templates no deben contener lógica de negocio ni consultas SQL.

Usar consultas SQL parametrizadas.

## Productos

Existen dos tipos:

- UNIDAD
- PESO

UNIDAD:
unidad_stock = UNIDAD

PESO:
unidad_stock = G

Los productos por PESO guardan cantidades operativas en gramos.

La interfaz puede mostrar gramos o kilogramos.

No borrar físicamente productos.

Para retirar un producto:

activo = 0

Debe poder reactivarse posteriormente.

El código/EAN de un producto no se modifica después de su creación.

Los datos SEPA de referencia son de solo lectura.

El usuario puede modificar los campos operativos de su comercio.

`stock_actual` NO se modifica desde el formulario de productos.

`stock_minimo` sí puede configurarse desde el producto.

El stock actual solo podrá cambiar mediante:

- stock inicial;
- reposición;
- ajuste;
- venta;
- anulación de venta.

Estas operaciones se implementarán en versiones posteriores.

## Precios

`precio_venta_actual` es editable.

Si el usuario lo modifica:

precio_venta_confirmado = 1

`precio_compra_actual` es editable y puede ser NULL.

Si el usuario lo modifica:

precio_compra_confirmado = 1

`precio_compra_referencia` es únicamente una referencia SEPA mayorista.

No debe tratarse como costo contable confirmado.

Un producto nuevo debe tener precio de venta válido y mayor o igual a 0.

## Productos manuales

Un producto creado manualmente debe identificarse con:

origen_catalogo = MANUAL

El sistema deberá generar un código interno único si el producto no posee EAN.

El código interno no debe colisionar con los códigos existentes.

## Ventas — reglas para versiones futuras

El stock NO se modifica mientras se arma el carrito.

Solo se modifica al confirmar una venta.

Una venta debe confirmarse dentro de una transacción SQLite.

La confirmación futura deberá:

1. crear `ventas`;
2. crear `detalle_venta`;
3. actualizar stock;
4. registrar `movimientos_stock`;
5. hacer COMMIT.

Ante cualquier error:

ROLLBACK.

En `detalle_venta` deben guardarse el precio y costo utilizados en el momento de la venta.

Nunca recalcular una venta histórica utilizando precios actuales.

La anulación de una venta no debe eliminarla.

Debe cambiar:

estado = ANULADA

y restaurar stock mediante movimientos correspondientes.

## Seguridad y formularios

Validar siempre los datos en backend.

No confiar exclusivamente en validaciones HTML o JavaScript.

Usar protección CSRF en formularios que modifican información.

No aceptar precios negativos.

No aceptar cantidades negativas.

No aceptar tipos de venta diferentes de:

UNIDAD
PESO

## Alcance

No agregar frameworks, librerías o funcionalidades que no hayan sido solicitadas.

No implementar anticipadamente módulos correspondientes a versiones futuras.

Antes de realizar cambios arquitectónicos importantes, explicar primero el motivo.

Priorizar código sencillo, mantenible, testeable y fácil de comprender por estudiantes.