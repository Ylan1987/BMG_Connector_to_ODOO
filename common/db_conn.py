import sqlite3
import os # <-- Añadir esta línea
# Importamos las constantes desde el archivo de mapeos
from . import mapeos

def conectar_db():
    try:
        # --- DEBUG PRINT: Mostrar la ruta absoluta del archivo de la DB ---
        db_path = os.path.abspath(mapeos.DB_FILE)
        print(f"DEBUG_DB_PATH: Connecting to database at -> {db_path}")
        # ---------------------------------------------------------------
        conn = sqlite3.connect(mapeos.DB_FILE, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Error crítico al conectar con la base de datos SQLite: {e}")
        return None

def inicializar_db():
    """
    Crea la tabla si no existe y añade las columnas necesarias si faltan.
    Ahora es la fuente única de verdad para el esquema de la DB.
    """
    print("🔧 Verificando y actualizando esquema de la base de datos...")
    conn = conectar_db() 
    if not conn:
        print("❌ No se pudo conectar a la base de datos para inicializarla.")
        return
    
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trabajos (
            order_code TEXT NOT NULL, line_number INTEGER NOT NULL, estado TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
            intentos_fallidos INTEGER DEFAULT 0, publisher_facility TEXT, publisher_id TEXT, title_id TEXT,
            ruta_archivo_tapa TEXT, ruta_archivo_contenido TEXT, order_date TEXT, client_reference TEXT,
            business_unit TEXT, publisher_name TEXT, order_type TEXT, run TEXT, line_status TEXT, code TEXT,
            title TEXT, line_status_date TEXT, delivery_date TEXT, quantity_requested INTEGER, total_pages INTEGER,
            height REAL, width REAL, bleed REAL, spine REAL, weight REAL, bw_paper_type TEXT, cover_paper_type TEXT,
            laminate TEXT, binding TEXT, datos_envio_json TEXT, publisher_observations TEXT, cover_printing_type TEXT,
            color_insert TEXT, color_pages TEXT, flaps_code TEXT, flaps_width TEXT, color_paper_type TEXT,
            PRIMARY KEY (order_code, line_number)
        )
    ''')

    cursor.execute("PRAGMA table_info(trabajos)")
    columnas_existentes = [row['name'] for row in cursor.fetchall()]

    columnas_deseadas = {
        'estado_odoo': "TEXT DEFAULT 'PENDIENTE'", 'odoo_opportunity_id': 'INTEGER',
        'odoo_sale_order_id': 'INTEGER', 'channel': 'TEXT', 'billing_number': 'TEXT',
        'bw_pages': 'INTEGER', 'sealing': 'TEXT', 'printing_facility': 'TEXT',
        'line_status_id': 'INTEGER', 'odoo_product_variant_id': 'INTEGER',
        'descripcion_detalle_libro': 'TEXT', 'estado_fabricacion': "TEXT DEFAULT 'PENDIENTE'",
        'odoo_mrp_order_id': 'INTEGER', 'odoo_sale_order_name': 'TEXT',
        'odoo_procurement_group_id': 'INTEGER', 'papel_tapa_size': 'TEXT',
        'interior_layout': 'TEXT', 'interior_papel_folder': 'TEXT', 'copias_calculadas': 'INTEGER',
        'unit_price': 'REAL', 'unit_price_adjustment': 'REAL', 'unit_currency': 'TEXT',
        'unit_currency_exchange': 'REAL', 'unit_price_invoice': 'REAL',
        'unit_price_channel': 'REAL', 'additional_services': 'REAL', 'usd_exchange': 'REAL',
        'shipping_cost_order': 'REAL', 'shipping_cost_order_adjustment': 'REAL',
        'shipping_cost_currency': 'TEXT', 'shipping_cost_instruction': 'REAL',
        'odoo_partner_id': 'INTEGER',
        'odoo_sale_order_line_id': 'INTEGER',
        'odoo_pickings_data_json': 'TEXT',
        'estado_interior_produccion': "TEXT DEFAULT 'PENDIENTE'", # Nueva columna para Script 06
        'estado_tapa_produccion': "TEXT DEFAULT 'PENDIENTE'",      # Nueva columna para Script 07
        'odoo_project_task_id': 'INTEGER', # Nueva columna para Script 02/08
        'intentos_fallidos_tapa': 'INTEGER DEFAULT 0', # Contador de fallos para Script 07
        'intentos_fallidos_interior': 'INTEGER DEFAULT 0', # Contador de fallos para Script 06
        'ruta_trabajo': 'TEXT', # Ruta a la carpeta del trabajo, guardada por Script 07
        'meli_status': 'TEXT', # Estado de la orden en Mercado Libre
        'x_origen_pais': 'TEXT',
        'x_precio_canal': 'REAL',
        'x_costo_impresion_uy': 'REAL',
        'x_comision_traer_libreria_uy': 'REAL',
        'x_comision_traer_editor_uy': 'REAL',
        'x_comision_editor_uy': 'REAL',
        'x_comision_traer_editor_bmg': 'REAL',
        'x_comision_editor_bmg': 'REAL',
        'x_comision_bmg_propia': 'REAL',
        'x_total_bmg_terceros': 'REAL',
        'x_total_bmg_propio': 'REAL',
        'x_total_lad_uy': 'REAL'
    }

    for nombre_col, tipo_col in columnas_deseadas.items():
        if nombre_col not in columnas_existentes:
            print(f"  - Añadiendo columna faltante: '{nombre_col}'")
            cursor.execute(f"ALTER TABLE trabajos ADD COLUMN {nombre_col} {tipo_col}")
    
    # --- Creación de la tabla de caché ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS odoo_cache (
            odoo_url TEXT NOT NULL,
            attribute_name TEXT NOT NULL,
            value_name TEXT NOT NULL,
            odoo_id INTEGER NOT NULL,
            PRIMARY KEY (odoo_url, attribute_name, value_name)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Esquema de la base de datos actualizado.")
