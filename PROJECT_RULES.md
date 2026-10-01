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
- ajuste por conteo;
- descuento de stock;
- venta;
- anulación de venta.

Venta y anulación de venta se implementarán en versiones posteriores.

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

---

## Inventario — reglas obligatorias desde v0.2

El stock nunca debe modificarse directamente desde el formulario de Productos.

Todo cambio de `stock_actual` debe tener una causa registrada en `movimientos_stock`.

Las operaciones de inventario previstas son:

- STOCK INICIAL
- REPOSICIÓN
- AJUSTE
- VENTA
- ANULACIÓN

En v0.2 solamente se implementan:

- stock inicial;
- reposición;
- ajuste por conteo;
- descuento de stock.

VENTA y ANULACIÓN se implementarán en versiones posteriores.

### Stock inicial

El stock inicial solamente puede registrarse cuando:

stock_actual IS NULL

Una vez inicializado, no debe volver a utilizarse la operación "Registrar stock inicial".

El registro debe:

1. actualizar `productos.stock_actual`;
2. insertar un registro en `movimientos_stock`.

Usar:

tipo = 'AJUSTE'
motivo = 'STOCK_INICIAL'

Ambas operaciones deben ejecutarse dentro de la misma transacción SQLite.

### Reposición

Una reposición representa mercadería que ingresa al negocio.

Debe:

1. requerir que el stock ya esté inicializado;
2. aceptar únicamente cantidades mayores que cero;
3. sumar la cantidad al stock actual;
4. crear un movimiento de stock.

Usar:

tipo = 'ENTRADA'
motivo = 'REPOSICION'

Nunca reemplazar directamente el stock con la cantidad recibida.

Ejemplo:

stock actual = 20
reposición = 10
stock resultante = 30

### Ajuste por conteo

Un ajuste por conteo se utiliza cuando el stock físico real es diferente al registrado.

El usuario debe ingresar el STOCK REAL contado, no la diferencia.

Ejemplo:

stock registrado = 20
stock real = 18

El sistema calcula:

diferencia = -2

Debe guardar:

stock_actual = 18

y registrar:

tipo = 'AJUSTE'
motivo = 'DIFERENCIA_INVENTARIO'
cantidad = -2

El ajuste por conteo puede aumentar o disminuir stock.

Ejemplo de aumento:

stock registrado = 20
stock real = 23
diferencia = +3
stock_actual = 23
cantidad = +3

Si el stock real coincide con el stock registrado, la operación se rechaza.

Nunca permitir un stock real negativo.

En este formulario no se elige un motivo de pérdida. El motivo guardado es siempre DIFERENCIA_INVENTARIO.

Rotura, vencimiento, merma, consumo interno y otras salidas conocidas se registran con la operación de descuento.

### Descuento de stock

Un descuento registra una cantidad conocida que sale del inventario y no es una venta.

El usuario ingresa la cantidad a descontar. Esa cantidad debe ser mayor que cero.

El resultado no puede ser negativo:

cantidad a descontar <= stock actual

Ejemplo:

stock actual = 20
descontar = 2
stock resultante = 18

Debe guardar:

tipo = 'AJUSTE'
cantidad = -2

La cantidad del movimiento se guarda en negativo. El usuario no ingresa el signo.

Descontar hasta dejar el stock en cero es válido.

Motivos permitidos:

- ROTURA
- VENCIMIENTO
- MERMA
- CONSUMO_INTERNO
- OTRO

DIFERENCIA_INVENTARIO no se usa en el descuento. Queda reservado al ajuste por conteo.

La interfaz debe mostrar nombres amigables al usuario.

Requiere que el stock ya esté inicializado.

Un producto inactivo con stock inicializado puede descontar y también puede ajustar por conteo. No puede registrar stock inicial ni reponer.

### Productos por UNIDAD

Cuando:

tipo_venta = 'UNIDAD'

entonces:

unidad_stock = 'UNIDAD'

Stock inicial, reposición, ajuste por conteo y descuento deben usar cantidades enteras.

No aceptar:

1.5 unidades

Sí aceptar:

1
2
15
100

### Productos por PESO

Cuando:

tipo_venta = 'PESO'

entonces:

unidad_stock = 'G'

La base operacional siempre almacena cantidades en gramos.

Ejemplos:

250 g → 250
1 kg → 1000
1,5 kg → 1500

La interfaz puede mostrar gramos o kilogramos de forma amigable.

No cambiar la unidad almacenada en SQLite.

### Atomicidad

Toda operación que modifique stock debe ejecutarse dentro de una transacción SQLite.

Flujo obligatorio:

BEGIN
→ validar producto y stock
→ actualizar `productos.stock_actual`
→ insertar `movimientos_stock`
→ COMMIT

Ante cualquier error:

ROLLBACK

Nunca puede existir una situación donde:

- cambió el stock pero no se creó el movimiento;
- se creó el movimiento pero no cambió el stock.

### Historial

`movimientos_stock` es la fuente de trazabilidad del inventario.

No borrar movimientos históricos.

El usuario debe poder consultar el historial de movimientos de un producto.

Cada movimiento debe conservar:

- producto;
- fecha y hora;
- tipo;
- cantidad;
- unidad;
- motivo;
- venta_id cuando corresponda en versiones futuras.

### Stock mínimo

`stock_minimo` es una configuración del producto.

No constituye un movimiento de inventario.

Puede editarse desde Productos.

Cuando:

stock_actual <= stock_minimo

el producto debe considerarse con stock bajo.

Un producto con:

stock_actual IS NULL

no debe considerarse stock bajo; significa que todavía no se inicializó el inventario.

Un producto con:

stock_actual = 0

ya tiene el inventario inicializado, pero no quedan existencias.
En el listado se muestra como "Sin existencias".
Si además tiene stock mínimo y el stock no lo supera, sigue entrando en el filtro de stock bajo.

### Seed

La base:

data/seed/kiosco_merlo_sepa.sqlite

continúa siendo inmutable.

Todas las operaciones de inventario se realizan exclusivamente sobre la base operacional de `instance/`.

Nunca ejecutar pruebas de escritura contra la seed.