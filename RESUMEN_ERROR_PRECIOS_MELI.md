# Resumen de Diagnóstico y Plan de Acción: Error de Precios en Múltiples Líneas

## 1. Problema Principal
Ciertos pedidos de Mercado Libre que tienen más de una línea de producto (múltiples artículos) no están actualizando los precios correctamente en Odoo. El sistema solo ajusta el precio del primer artículo del pedido y deja los siguientes con el precio incorrecto que viene de BMG.

## 2. Pedidos Afectados Identificados
*   **Pedido BMG:** `659990`
*   **Pedido BMG:** `660061`

## 3. Causa Raíz del Problema (El Bug)
El error se encuentra en el script `script_03_crear_ordenes_venta_odoo.py`. La lógica actual es defectuosa por dos razones:
1.  **Toma solo el primer item:** Siempre selecciona el primer artículo (`order_items[0]`) de la respuesta de la API de Mercado Libre, sin importar qué línea de BMG se esté procesando.
2.  **Se desactiva a sí misma:** Después de procesar la primera línea, la línea `datos_meli = None` anula los datos de Mercado Libre, impidiendo cualquier ajuste de precio para las líneas subsecuentes del mismo pedido.

El código no tiene un mecanismo para asociar (hacer "match") cada línea de BMG con su correspondiente línea de Mercado Libre.

## 4. Plan de Acción

### Paso 1: Probar la Lógica de "Matching"

El objetivo es confirmar que podemos asociar de forma fiable cada línea de BMG con su par en Mercado Libre. El campo clave para esto es el `seller_sku` de Mercado Libre, que debería contener el `TitleID` de BMG (sin el prefijo `PAP`).

**Cómo probarlo manualmente:**
1.  Obtener los detalles del pedido `659990` de la API de BMG para ver la lista de `TitleID` de sus líneas.
2.  Obtener los detalles del pedido de Meli correspondiente (`2000017024811070`) de la API de Mercado Libre para ver la lista de `order_items` y sus `seller_sku`.
3.  Comparar visualmente: por cada `TitleID` de BMG, debe existir un `seller_sku` en Mercado Libre que lo contenga.

### Paso 2: Implementar la Solución en el Código

Si la prueba de matching es exitosa, la solución es refactorizar la sección de ajuste de precios en `script_03_crear_ordenes_venta_odoo.py`.

**Lógica a implementar:**
1.  Dentro del bucle `for trabajo in grupo_trabajos:` (que recorre cada línea de BMG):
2.  Obtener y limpiar el `TitleID` de la línea de BMG actual (ej. `PAP12345` -> `12345`).
3.  Buscar en la lista de `order_items` de Mercado Libre un item cuyo `seller_sku` contenga ese `TitleID` limpio.
4.  **Si se encuentra una coincidencia:**
    *   Tomar el `unit_price` de ese item de Mercado Libre.
    *   Ajustar el precio en la variable de la línea de BMG (`trabajo['price']`).
    *   **Crucial:** "Marcar como usado" o eliminar ese item de la lista de Mercado Libre para que no se vuelva a usar por error en la siguiente línea del mismo pedido.
5.  **Si no se encuentra coincidencia:** Registrar una advertencia (`_logger.warning`) y continuar con el precio original de BMG para esa línea, sin ajustar.
6.  **Eliminar la línea `datos_meli = None`** que actualmente detiene el proceso.
7.  Añadir logging detallado a todo este nuevo proceso para poder verificar su comportamiento en el futuro.

