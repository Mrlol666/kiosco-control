# Base inicial Kiosco Control — DIA Merlo + SEPA Mayorista

## Qué contiene
Esta base fue preparada para arrancar el desarrollo del proyecto Kiosco Control.

- Catálogo principal: **4313 productos únicos** de Supermercados DIA Merlo.
- Sucursales minoristas usadas: **DIA 28 - MERLO** y **DIA 64 - MERLO**.
- Ambos locales informan los mismos 4313 códigos de producto; se conservaron los dos precios cuando difieren.
- Diferencias de precio entre las dos sucursales DIA: **29 productos**.
- Productos con coincidencia EAN exacta en SEPA Mayorista: **2575** (59.7%).
- Coincidencias con mayoristas cercanos/Zona Oeste: **2383**.
- Coincidencias adicionales usando otras sucursales mayoristas del país como referencia: **192**.
- Sin coincidencia mayorista exacta: **1738**.
- Productos preparados como venta por peso: **142**.
- Productos por unidad: **4171**.

## Mayoristas cercanos priorizados
Para `precio_compra_referencia` se priorizaron ofertas de:
1. MAXICONSUMO — Sucursal Merlo.
2. NINI — Moreno / Paso del Rey.
3. YAGUAR — Moreno.
4. MAKRO — Ituzaingó.

Si un EAN no aparecía en esas sucursales, se buscó una coincidencia exacta en el resto del archivo mayorista y se marcó `alcance_precio_compra = NACIONAL`.

**Importante:** `precio_compra_referencia` es un precio mayorista SEPA, no demuestra cuánto pagó un kiosquero real. Debe tratarse como dato inicial/de referencia.

## Archivos
- `kiosco_merlo_sepa.sqlite`: base SQLite lista para usar desde Python/Flask/FastAPI.
- `productos_dia_merlo_combinado.csv`: tabla principal en formato fácil de revisar.
- `precios_minoristas_dia_merlo.csv`: los dos precios DIA por sucursal.
- `precios_mayoristas_match.csv`: todas las ofertas mayoristas con EAN coincidente.
- `schema_kiosco.sql`: esquema SQL reproducible.

## Tabla `productos`
Los campos principales para la aplicación son:
- `producto_id`: clave interna.
- `codigo_ean`: **TEXT**, nunca INTEGER. Hay códigos con ceros a la izquierda.
- `descripcion`, `marca`, `categoria`.
- `tipo_venta`: `UNIDAD` o `PESO`.
- `unidad_stock`: `UNIDAD` o `G`.
- `precio_venta_actual`: inicializado con el precio DIA sucursal 64.
- `precio_venta_confirmado`: empieza en 0; el kiosquero puede confirmar/editar.
- `precio_compra_referencia`: mejor referencia mayorista encontrada.
- `precio_compra_actual`: solo se precarga cuando la referencia mayorista es menor que el precio de venta; si no, queda NULL.
- `precio_compra_confirmado`: empieza en 0.
- `stock_actual` y `stock_minimo`: quedan NULL porque SEPA no publica el inventario real del kiosco.
- `calidad_dato`: avisa anomalías o productos que requieren revisión.

## Productos por peso
Se marcaron como `PESO` los productos DIA con código de circulación variable que se informan a **1 KG**, por ejemplo fiambres, quesos, frutas, verduras y panificados a granel.

Regla para la app:
- La interfaz puede mostrar kg/g.
- La base operacional debe guardar el stock en **gramos**.
- Si se venden 250 g, el carrito guarda `cantidad = 250` y `unidad_cantidad = 'G'`.
- El stock se descuenta recién al confirmar la venta.

## Precios
`precio_venta_actual` es una semilla para desarrollo, no el precio obligatorio del futuro kiosco.

`precio_compra_actual` se inicializa solo cuando:
`precio_compra_referencia < precio_venta_actual`.

Los productos con referencias sospechosas siguen conservando la oferta en `precios_mayoristas`, pero no se fuerza un costo operacional incorrecto.

## Tablas operativas listas para desarrollar
La base ya incluye vacías:
- `ventas`
- `detalle_venta`
- `movimientos_stock`
- `gastos`
- `medios_pago`

También incluye:
- `vw_productos_margen`
- `vw_stock_bajo`

## Ejemplos SQL

### Buscar producto
```sql
SELECT producto_id, codigo_ean, descripcion, marca, precio_venta_actual, stock_actual
FROM productos
WHERE activo = 1
  AND descripcion LIKE '%COCA%';
```

### Ver productos con costo mayorista utilizable
```sql
SELECT descripcion, precio_compra_actual, precio_venta_actual,
       ROUND(precio_venta_actual - precio_compra_actual, 2) AS margen
FROM productos
WHERE precio_compra_actual IS NOT NULL
ORDER BY margen DESC;
```

### Productos por peso
```sql
SELECT producto_id, codigo_ean, descripcion, precio_venta_actual
FROM productos
WHERE tipo_venta = 'PESO' AND activo = 1;
```

## Reglas para Cursor / Grok
1. No cambiar `codigo_ean` a INTEGER.
2. No borrar físicamente productos con ventas históricas: usar `activo = 0`.
3. Una venta debe guardarse dentro de una transacción SQLite.
4. El stock se modifica solo al confirmar/anular ventas o registrar entradas/ajustes.
5. Para productos `PESO`, manejar stock y cantidades en gramos.
6. Guardar en `detalle_venta` el precio y costo usados en el momento de la venta; no recalcular ventas históricas con precios actuales.
7. `precio_compra_referencia` no es un costo contable confirmado.
