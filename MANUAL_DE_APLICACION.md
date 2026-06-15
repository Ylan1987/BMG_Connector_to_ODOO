# Manual de Aplicación: Sistema de Sincronización BMG a Odoo

## 1. Resumen General

Este sistema automatiza el flujo de pedidos desde Bibliomanager (BMG) hasta Odoo, gestionando la creación y actualización de pedidos de venta, albaranes, órdenes de fabricación y tareas de producción. El objetivo principal es reducir la carga de trabajo manual y garantizar la coherencia de los datos entre ambos sistemas.

## 2. Flujo de Datos y Componentes Principales

La aplicación se compone de varios scripts Python que se ejecutan en una secuencia orquestada. La base de datos `trabajos.db` (SQLite local) actúa como un intermediario central para mantener el estado y los datos de los pedidos.

### 2.1. `00_orquestador.py`

**Función:** Es el script principal que coordina la ejecución de todos los demás scripts en la secuencia correcta. También se encarga de inicializar la base de datos local `trabajos.db` y su esquema.

**Condiciones de Ejecución:** Se ejecuta de forma programada para mantener el sistema actualizado.

**Secuencia de Ejecución:**
1.  `db_conn.inicializar_db()`: Asegura que la DB local tenga la estructura correcta.
2.  `script_01_sincronizar_pedidos_bmg.py`: Obtiene pedidos nuevos de BMG.
3.  `script_03_crear_ordenes_venta_odoo.py`: Crea Pedidos de Venta en Odoo.
4.  `script_02_actualizar_estados_bmg.py`: Actualiza estados de pedidos existentes en Odoo (CRM, Tareas).
5.  `script_04_confirmar_ventas_y_crear_pickings.py`: Confirma ventas y crea albaranes en Odoo.
6.  `script_07_generar_tapa_produccion.py`: Genera archivos de producción para tapas.
7.  `script_06_generar_interior_produccion.py`: Genera archivos de producción para interiores.
8.  `script_05_crear_ordenes_fabricacion.py`: Crea Órdenes de Fabricación en Odoo.

### 2.2. `script_01_sincronizar_pedidos_bmg.py`

**Función:** Se conecta a la API WSDL de BMG para obtener pedidos nuevos o actualizados (generalmente de las últimas 24 horas). Almacena los detalles completos de cada línea de pedido en la tabla `trabajos` de la base de datos local `trabajos.db`.

**Genera:** Registros en la tabla `trabajos` de la DB local.
**Condiciones:** Procesa solo pedidos que no existen previamente en la DB local (`trabajos`).

### 2.3. `script_02_actualizar_estados_bmg.py`

**Función:** Monitorea los pedidos en `trabajos.db` que aún no han sido finalizados. Consulta la API de BMG para obtener el estado más reciente de cada línea de pedido y actualiza la DB local (`line_status`, `line_status_id`). Si se detectan cambios de estado, realiza acciones en Odoo (actualización de etapa de Oportunidad, creación/cierre de actividades, movimiento de tareas de proyecto) y notifica a BMG si es necesario.

**Genera:** Actualizaciones en `trabajos.db` y acciones en Odoo (CRM, Project Tasks, `bmg.notification.queue`).
**Condiciones:** Procesa pedidos con estados intermedios.

### 2.4. `script_03_crear_ordenes_venta_odoo.py`

**Función:** Lee pedidos de `trabajos.db` que están listos para ser sincronizados con Odoo. Crea `crm.lead` (Oportunidades), `res.partner` (clientes si son de MercadoLibros) y `sale.order` (Pedidos de Venta) en Odoo. Maneja la creación de variantes de productos dinámicamente y calcula descuentos.

**Genera:** Oportunidades, Clientes (para ML), Pedidos de Venta y sus líneas en Odoo. Actualiza `trabajos.db` con los IDs de Odoo.
**Condiciones:**
*   **Editor Uruguayo:** Si `publisher_facility` es 'LAD'.
*   **Facturación a Bibliomanager:** Si el pedido no es `'eDistrib. 1 a 1'` Y `publisher_facility` no es 'LAD', el cliente se asigna a 'BIBLIOMANAGER'.
*   **Validación de Diseño:** Se añade una línea de validación de diseño al pedido de venta si el `order_type` es `'1ra. impr. std'` Y el editor es Uruguayo (`publisher_facility == 'LAD'`).
*   **Descripción de Línea de Envío:** Incluye campos como 'Tipo de envío', 'Operador', 'Empresa', 'Destino', etc.

### 2.5. `script_04_confirmar_ventas_y_crear_pickings.py`

**Función:** Confirma Pedidos de Venta en Odoo que ya tienen sus líneas y variantes creadas. Para cada línea de pedido, genera los albaranes (`stock.picking`) necesarios. Mueve las oportunidades a la etapa "Ganado con OT" y, si procede, actualiza las tareas de validación de diseño asociadas.

**Genera:** Confirmación de `sale.order` y creación de `stock.picking` y `stock.move` en Odoo. Actualizaciones de etapas de Oportunidades.
**Condiciones:**
*   Procesa pedidos que tienen `odoo_sale_order_id` pero aún no tienen `odoo_pickings_data_json`.
*   Solo confirma si el estado BMG (`line_status_id`) es confirmable.
*   **Descripción de Línea de Albarán:** El campo `description_picking` en cada `stock.move` (línea del albarán) se rellena con las dos primeras líneas de la descripción detallada del libro.
*   **Flag BMG en Albarán:** El albarán principal (`stock.picking`) tiene el campo `x_is_bmg_picking` establecido a `True` para identificar que es un albarán generado por el sistema BMG.

### 2.6. `script_05_crear_ordenes_fabricacion.py`

**Función:** Crea Órdenes de Fabricación (`mrp.production`) en Odoo para los trabajos que ya tienen albaranes creados y están listos para fabricación. Genera Listas de Materiales (LdM) dinámicamente para cada componente (tapa, interior, libro final). Luego, confirma estas OFs en cascada, incluyendo sus sub-OFs generadas por Odoo.

**Genera:** `mrp.bom`, `mrp.production` (principal y sub-órdenes) en Odoo.
**Condiciones:**
*   Procesa trabajos con pickings creados, sin OF, y con estados de producción de tapa e interior generados.
*   **Omisión para Producción Externa:** No genera OFs si el `printing_facility` no es 'LAD' (editor no uruguayo).
*   **Nomenclatura de OFs:**
    *   **OF principal:** Su `name` se establece como `[código_pedido]-[número_línea] [título_libro]`.
    *   **OFs hijas (tapa e interior):** Sus `name` se establecen como `[código_pedido]-[número_línea] tapa de [título_libro]` o `[código_pedido]-[número_línea] interior de [título_libro]`.
*   **Carga de Estados en Operaciones:** Asegura que `estado_en_progreso` y `estado_completado` para las operaciones de fabricación se carguen correctamente según si el `order_type` es `eDistrib. 1 a 1` o `POD`.

### 2.7. `script_06_generar_interior_produccion.py`

**Función:** Genera archivos PDF de producción para los interiores de los libros. Lee los datos de la DB local para determinar qué interiores necesitan ser generados. Utiliza PyMuPDF (`fitz`) y `pypdf` para manipular los PDFs, añadir marcas de corte, códigos de barras y una hoja de orden de trabajo. Guarda los archivos generados en rutas de red específicas. Notifica en Odoo (Chatter) y por email sobre el éxito o el fallo.

**Genera:** Archivos PDF de interior de producción. Mensajes en Chatter de Odoo.
**Condiciones:** Procesa trabajos con tapa generada y ruta de trabajo definida.

### 2.8. `script_07_generar_tapa_produccion.py`

**Función:** Similar al script 06, pero para la generación de archivos PDF de tapas. También se encarga de encontrar la ruta de la carpeta de trabajo del pedido en el servidor. Procesa el PDF de la tapa original, añade información y códigos de barras. Guarda los archivos generados en rutas de red específicas. Notifica en Odoo (Chatter) y por email.

**Genera:** Archivos PDF de tapa de producción. Rutas de trabajo en `trabajos.db`. Mensajes en Chatter de Odoo.
**Condiciones:** Procesa trabajos con pickings creados.

### 2.9. `script_08_crear_tarjeta_proyecto.py`

**Función:** Un script auxiliar (probablemente llamado por script 02 o script 03) para crear una tarea (`project.task`) en un proyecto específico de Odoo (ej. "[Pre-Producción] Validación del Diseño del cliente").

**Genera:** Tareas en Odoo (`project.task`).

### 2.10. `common/mapeos.py`

**Función:** Contiene todas las constantes de configuración, mapeos de IDs, estados, nombres de productos, rutas de archivos, credenciales de API (BMG, Odoo, SMTP), y otros parámetros críticos del sistema. Es la central de configuración del sistema.

### 2.11. `common/db_conn.py`

**Función:** Provee las funciones para conectarse a la base de datos SQLite local (`trabajos.db`) e inicializar su esquema. Asegura que la tabla `trabajos` y `odoo_cache` existan y tengan todas las columnas necesarias.

## 3. Lógica de Negocio Clave

*   **Sincronización:** Los pedidos de BMG se sincronizan con la DB local y luego se procesan hacia Odoo.
*   **Estados BMG:** Los estados de línea de BMG controlan el flujo de trabajo en Odoo (ej., aprobación de presupuesto, recepción de archivos, validación de diseño).
*   **Identificación de Editor Uruguayo:** Un editor se considera uruguayo si su `publisher_facility` es 'LAD'.
*   **Facturación:** Pedidos internacionales POD (no `eDistrib. 1 a 1` y no 'LAD') se facturan a 'BIBLIOMANAGER'.
*   **Validación de Diseño:** La tarea/línea de validación de diseño (`'Validación de diseños del cliente'`) solo se crea para pedidos de `'1ra. impr. std'` de editores uruguayos.
*   **Generación de Archivos:** La generación de archivos de producción (tapa e interior) ocurre después de la confirmación de la venta y la creación de pickings.
*   **Manejo de Fallos:** Los fallos en la búsqueda/generación de archivos son gestionados con reintentos, mensajes en Chatter de Odoo y, si son persistentes, con notificaciones por email.

---
