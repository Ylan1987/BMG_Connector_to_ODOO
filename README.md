# BMG Connector to Odoo (v2.0)

Bienvenido al repositorio oficial del **Orquestador BMG-Odoo**. 
Este sistema es un middleware de automatización diseñado para sincronizar, gestionar y orquestar todo el flujo de pedidos y producción entre la plataforma **Bibliomanager (BMG)** y el ERP **Odoo** de la imprenta.

## 🎯 Objetivo del Sistema
El objetivo principal de este desarrollo es eliminar la carga manual de "data entry", garantizando que cada vez que ingresa un pedido firme a BMG, este viaje de forma automática a Odoo, donde se le crean:
- **Oportunidades (CRM)**
- **Pedidos de Venta (Sales Orders)**
- **Albaranes de Entrega (Pickings)**
- **Órdenes de Fabricación en Cascada (MRPs para Tapa, Interior y Ensobrado)**

A su vez, el sistema genera dinámicamente los **PDFs de Producción** (imponiendo códigos de barra, expandiendo márgenes de corte y adjuntando hojas de ruta) para que los operarios de planta solo tengan que imprimir.

---

## ⚙️ Arquitectura y Componentes
El corazón del sistema es el **`00_orquestador.py`**, el cual se ejecuta periódicamente (cron/tarea programada) y desencadena una cadena de 8 scripts secuenciales. Utiliza una base de datos local SQLite (`trabajos.db`) como memoria caché y estado intermedio para saber exactamente en qué fase se encuentra cada pedido sin saturar las APIs.

### La Secuencia de Scripts:
1. **`Script 01` (Sincronización):** Se conecta a BMG (vía SOAP/WSDL) para detectar pedidos nuevos y guardarlos localmente.
2. **`Script 03` (Ventas en Odoo):** Toma los pedidos locales nuevos y crea los `sale.order` en Odoo, generando productos y variantes al vuelo si no existen.
3. **`Script 02` (Monitoreo de Estados):** Escucha permanentemente a BMG para ver si los pedidos avanzan (ej. de "Pendiente de Archivos" a "Muestra Aprobada"). Al detectar un avance, notifica a Odoo y mueve las tarjetas del CRM.
4. **`Script 04` (Confirmación y Albaranes):** Cuando el pedido está listo, aprieta el botón de "Confirmar" en Odoo, lo que genera los Pickings de stock.
5. **`Script 07` (Preimpresión Tapas):** Busca los PDFs originales en el servidor, les inserta el código de barras ajustado dinámicamente, y los guarda en la carpeta de la máquina de impresión.
6. **`Script 06` (Preimpresión Interiores):** Mismo proceso para los interiores de los libros.
7. **`Script 05` (Producción MRP):** Crea las Órdenes de Fabricación en Odoo con sus respectivas Listas de Materiales (LdM/BoM) exactas según el tipo de papel, encuadernación y cantidad.
8. **`Script 08` (Sincronización Mercado Libre):** Script independiente que actualiza los estados de envío de los paquetes despachados vía Mercado Libre.

---

## 🛠️ Tecnologías Utilizadas
- **Python 3.10+** (Lógica core, manipulación de APIs)
- **OdooRPC / XML-RPC** (Comunicación con el ERP Odoo)
- **Zeep** (Cliente SOAP para consumir la API de Bibliomanager)
- **PyMuPDF (fitz) y pypdf** (Manipulación y ensamblaje de PDFs de producción)
- **SQLite3** (Base de datos transaccional local)

---

## 📚 Documentación Adicional
- Para ver el detalle técnico exhaustivo de cada campo y función, consultar el [MANUAL_DE_APLICACION.md](./MANUAL_DE_APLICACION.md).
- Para ver el registro histórico de parches y decisiones de diseño tomadas recientemente, consultar el [GEMINI.md](./GEMINI.md).
