import csv
import re
import sqlite3
import subprocess
import os
import argparse
import base64
import odoorpc
from datetime import datetime
import sys; import os; sys.path.append(os.path.abspath("..")); from common.mapeos import ODOO_URL, ODOO_DB, ODOO_USUARIO, ODOO_CONTRASENA

DB_PATH = 'cortes_optimos.db'
DB_GESTION_PATH = 'gestion_fabricacion.db'
lote_size = 500  # Consultar de 25 en 25 para no sobrecargar la API (REDUCIDO)
LOTE_ESCRITURA_PDF = 500 # Tamaño del lote para procesar LdMs
    
def inicializar_db_gestion():
    """Crea las tablas para la gestión de productos generados si no existen."""
    with sqlite3.connect(DB_GESTION_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS papeles_padre (
                id INTEGER PRIMARY KEY,
                external_id TEXT UNIQUE NOT NULL,
                nombre_original TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hijos_generados (
                id INTEGER PRIMARY KEY,
                papel_padre_id INTEGER NOT NULL,
                corte_ancho REAL NOT NULL,
                corte_alto REAL NOT NULL,
                fecha_creacion TEXT,
                FOREIGN KEY (papel_padre_id) REFERENCES papeles_padre (id),
                UNIQUE (papel_padre_id, corte_ancho, corte_alto)
            )
        """)
    print("✅ Base de datos de gestión inicializada.")

def conectar_odoo():
    """Se conecta a la API de Odoo y devuelve el objeto de la API."""
    try:
        odoo = odoorpc.ODOO(ODOO_URL, protocol='jsonrpc+ssl', port=443, timeout=120)
        odoo.login(ODOO_DB, login=ODOO_USUARIO, password=ODOO_CONTRASENA)
        print("✅ Conexión a Odoo establecida.")
        return odoo
    except Exception as e:
        print(f"❌ Error crítico al conectar con Odoo: {e}")
        return None

from collections import defaultdict

def adjuntar_pdfs_faltantes(odoo, forzar=False):
    """
    Adjunta PDFs a las operaciones de LdMs de corte de papel.
    1. Busca LdMs por ID externo que empiece con __export__.mrp_bom_creacion_de_pliego
    2. Extrae las dimensiones del ID externo para construir el nombre del PDF
    3. Actualiza en lotes máximos de 100 operaciones por llamada
    """
    print("\n--- 📎 Iniciando proceso para adjuntar PDFs faltantes a LdMs ---")
    if forzar:
        print("  - ⚠️ MODO FORZADO ACTIVADO: Se intentará actualizar el PDF de TODAS las operaciones de corte.")
    
    data_model = odoo.env['ir.model.data']
    operation_model = odoo.env['mrp.routing.workcenter']

    # PASO 1: Buscar LdMs por ID externo
    print("  - Paso 1: Buscando LdMs por ID externo...")
    try:
        data_records = data_model.search_read(
            [('module', '=', '__export__'),
             ('model', '=', 'mrp.bom'),
             ('name', '=like', 'mrp_bom_creacion_de_pliego%')],
            ['res_id', 'name']
        )
        
        if not data_records:
            print("✅ No se encontraron LdMs de corte.")
            return
        
        print(f"  - Encontradas {len(data_records)} LdMs de corte.")
        bom_ids = [r['res_id'] for r in data_records]
        
    except Exception as e:
        print(f"❌ ERROR en Paso 1: {e}")
        return

    # PASO 2: Buscar operaciones
    if forzar:
        print("  - Paso 2: Buscando TODAS las operaciones (modo forzado)...")
        try:
            operaciones = operation_model.search_read(
                [('bom_id', 'in', bom_ids)],
                ['id', 'bom_id']
            )
            if not operaciones:
                print("✅ No se encontraron operaciones para las LdMs de corte.")
                return
            print(f"  - Encontradas {len(operaciones)} operaciones en total.")
        except Exception as e:
            print(f"❌ ERROR en Paso 2 (modo forzado): {e}")
            return
    else:
        print("  - Paso 2: Buscando operaciones sin PDF...")
        try:
            operaciones = operation_model.search_read(
                [('bom_id', 'in', bom_ids),
                 '|',
                 '&', ('worksheet_type', '=', 'pdf'), ('worksheet', '=', False),
                 ('worksheet_type', '!=', 'pdf')],
                ['id', 'bom_id']
            )
            
            if not operaciones:
                print("✅ No se encontraron operaciones sin PDF. Todo está actualizado.")
                return
                
            print(f"  - Encontradas {len(operaciones)} operaciones SIN PDF adjunto.")
            
        except Exception as e:
            print(f"❌ ERROR en Paso 2: {e}")
            return

    # PASO 3: Mapear operaciones a PDFs usando el ID externo
    print("  - Paso 3: Mapeando PDFs desde IDs externos...")
    
    # Crear un mapa de bom_id -> external_id_name
    bom_to_ext_id = {r['res_id']: r['name'] for r in data_records}
    
    # Agrupar operaciones por PDF
    pdf_a_operaciones = defaultdict(list)
    ops_sin_pdf = []
    
    for op in operaciones:
        op_id = op['id']
        bom_id = op['bom_id'][0]
        ext_id_name = bom_to_ext_id.get(bom_id)
        
        if not ext_id_name:
            ops_sin_pdf.append(op_id)
            continue
        
        try:
            # Parsear el ID externo
            # Ejemplo: mrp_bom_creacion_de_pliego_250x350cm_desde_papel_coteado_90gr._70x100cm
            # Patrón: ...pliego_([dimensiones])cm_desde_..._([dimensiones])cm
            match = re.search(r'pliego_([\d\.]+)x([\d\.]+)cm_desde_.*?([\d\.]+)x([\d\.]+)cm', ext_id_name)
            
            if not match:
                ops_sin_pdf.append(op_id)
                continue
            
            # Extraer dimensiones del corte y del pliego
            corte_w, corte_h = float(match.group(1)), float(match.group(2))
            pliego_w, pliego_h = float(match.group(3)), float(match.group(4))
            
            # Convertir a mm (multiplicar por 10)
            corte_w_mm = int(corte_w)
            corte_h_mm = int(corte_h)
            pliego_w_mm = int(pliego_w * 10)
            pliego_h_mm = int(pliego_h * 10)
            
            # Construir nombre del PDF: Corte_[pliego_mayor]x[pliego_menor]_[corte]x[corte].pdf
            pdf_filename = f"Corte_{max(pliego_w_mm, pliego_h_mm)}x{min(pliego_w_mm, pliego_h_mm)}_{corte_w_mm}x{corte_h_mm}.pdf"
            pdf_path = os.path.join('layouts_pdf', pdf_filename)
            
            pdf_a_operaciones[pdf_path].append(op_id)
            
        except Exception as e:
            print(f"    - ⚠️ Error parseando ID externo '{ext_id_name}': {e}")
            ops_sin_pdf.append(op_id)
    
    print(f"  - Mapeadas {sum(len(ops) for ops in pdf_a_operaciones.values())} operaciones a {len(pdf_a_operaciones)} PDFs.")
    if ops_sin_pdf:
        print(f"  - ⚠️ {len(ops_sin_pdf)} operaciones sin PDF identificado.")

    # PASO 4: Actualizar en lotes (máximo 100 operaciones por lote)
    print("\n  - Paso 4: Actualizando operaciones en lotes...")
    
    LOTE_MAXIMO = 100
    total_actualizadas = 0
    total_omitidas = 0
    
    for pdf_path, op_ids_completo in pdf_a_operaciones.items():
        # Verificar que el PDF existe
        if not os.path.exists(pdf_path):
            print(f"\n  -> ❌ PDF no encontrado: '{os.path.basename(pdf_path)}' ({len(op_ids_completo)} ops omitidas)")
            total_omitidas += len(op_ids_completo)
            continue
        
        # Leer y codificar el PDF una sola vez
        try:
            with open(pdf_path, "rb") as pdf_file:
                pdf_encoded = base64.b64encode(pdf_file.read()).decode('ascii')
        except Exception as e:
            print(f"\n  -> ❌ Error leyendo PDF '{os.path.basename(pdf_path)}': {e}")
            total_omitidas += len(op_ids_completo)
            continue
        
        # Dividir en lotes de LOTE_MAXIMO
        num_lotes = (len(op_ids_completo) + LOTE_MAXIMO - 1) // LOTE_MAXIMO
        
        print(f"\n  -> PDF: '{os.path.basename(pdf_path)}' ({len(op_ids_completo)} ops, {num_lotes} lotes)")
        
        for i in range(num_lotes):
            inicio = i * LOTE_MAXIMO
            fin = min((i + 1) * LOTE_MAXIMO, len(op_ids_completo))
            lote = op_ids_completo[inicio:fin]
            
            try:
                success = operation_model.write(lote, {
                    'worksheet_type': 'pdf',
                    'worksheet': pdf_encoded
                })
                if success:
                    print(f"     ✅ Lote {i+1}/{num_lotes}: {len(lote)} ops actualizadas (API devolvió True)")
                    total_actualizadas += len(lote)
                else:
                    print(f"     ❌ Lote {i+1}/{num_lotes}: Error - La API de Odoo devolvió False.")
                    total_omitidas += len(lote)
                
            except Exception as e:
                print(f"     ❌ Lote {i+1}/{num_lotes}: Error - {e}")
                total_omitidas += len(lote)
    
    print(f"\n--- ✅ Proceso finalizado ---")
    print(f"  Actualizadas: {total_actualizadas} operaciones")
    print(f"  Omitidas: {total_omitidas} operaciones")
def get_paper_info(row, headers):
    """Extrae la información relevante de una fila de CSV si es un producto de papel."""
    category_idx = headers.index('Categoría del producto/ID externo')
    if row[category_idx] == '__export__.product_category_materia_prima_papel':
        name_idx = headers.index('Nombre')
        name = row[name_idx]
        id_externo_idx = headers.index('ID')
        id_externo = row[id_externo_idx]

        grammage_match = re.search(r'(\d+)gr', name)
        size_match = re.search(r'(\d+[.,]?\d*)\s*x\s*(\d+[.,]?\d*)cm', name)
        
        if grammage_match and size_match:
            return {
                'grammage': grammage_match.group(1),
                'width': float(size_match.group(1).replace(',', '.')),
                'height': float(size_match.group(2).replace(',', '.')),
                'original_name': name,
                'external_id': id_externo
            }
    return None

def ensure_product_exists(odoo, row, headers):
    """Verifica si un producto existe en Odoo por su ID externo, si no, lo crea."""
    product_template_model = odoo.env['product.template']
    external_id = row[headers.index('ID')]
    
    # Intentar buscar por XML ID
    try:
        product_template = odoo.env.ref(external_id)
        if product_template:
            print(f"  -> Producto padre encontrado en Odoo: {product_template.name} (ID: {product_template.id})")
            return product_template.id
    except Exception:
        print(f"  -> No se encontró el producto padre con ID externo: {external_id}. Creándolo...")

    # Si no se encuentra, crearlo
    vals = {
        'name': row[headers.index('Nombre')],
        'type': 'product', # Almacenable
        'categ_id': odoo.env.ref('__export__.product_category_materia_prima_papel').id,
        'purchase_ok': True,
        'sale_ok': False,
    }
    try:
        new_template_id = product_template_model.create(vals)
        # Crear el XML ID para futuras referencias
        odoo.env['ir.model.data'].create({
            'name': external_id.split('.')[1],
            'module': external_id.split('.')[0],
            'model': 'product.template',
            'res_id': new_template_id,
        })
        print(f"  -> Producto padre CREADO: {vals['name']} (ID: {new_template_id})")
        return new_template_id
    except Exception as e:
        print(f"  -> ❌ Error al crear producto padre en Odoo: {e}")
        return None

def check_cache(db_path, p, mi, ma, inc):
    """Verifica si un análisis ya existe en la base de datos."""
    # Normaliza todas las dimensiones (mayor, menor) para que coincida con cómo
    # el optimizador guarda los datos. Esta es la corrección clave.
    p_w, p_h = max(p), min(p)
    mi_w, mi_h = max(mi), min(mi)
    ma_w, ma_h = max(ma), min(ma)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM analisis WHERE p_w=? AND p_h=? AND min_w=? AND min_h=? AND max_w=? AND max_h=? AND inc=?",
                       (p_w, p_h, mi_w, mi_h, ma_w, ma_h, inc))
        return cursor.fetchone()

def run_optimizer(pliego_cm):
    """Ejecuta el script optimizador_cortes.py si es necesario."""
    pliego_str = f"{pliego_cm[0]}x{pliego_cm[1]}"
    minimo_str = "21x30"
    maximo_str = pliego_str
    incremento_str = "0.1"
    
    print(f"  -> Ejecutando optimizador para pliego {pliego_str}...")
    command = [
        'python', 'optimizador_cortes.py',
        '--pliego', pliego_str,
        '--minimo', minimo_str,
        '--maximo', maximo_str,
        '--incremento', incremento_str
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("  -> Optimizador ejecutado con éxito.")
    except subprocess.CalledProcessError as e:
        print(f"  -> ❌ Error al ejecutar el optimizador:")
        print(e.stdout)
        print(e.stderr)
        raise

def fetch_results(db_path, analisis_id):
    """Obtiene los resultados de cortes óptimos para un análisis dado."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT ancho, alto, piezas FROM resultados WHERE analisis_id = ?", (analisis_id, ))
        return [dict(row) for row in cursor.fetchall()]

def create_child_product_and_bom(odoo, parent_product_id, parent_paper_info, cut_info):
    """Crea el producto hijo, su LdM y adjunta el PDF."""
    product_template_model = odoo.env['product.template']
    bom_model = odoo.env['mrp.bom']
    attachment_model = odoo.env['ir.attachment']

    grammage = parent_paper_info['grammage']
    cut_width = cut_info['ancho']
    cut_height = cut_info['alto']
    pieces = cut_info['piezas']

    # 1. Preparar nombre y IDs
    parent_base_name = parent_paper_info['original_name'].split(f" {grammage}gr")[0].strip()
    child_name = f"{parent_base_name} {grammage}gr {cut_width}x{cut_height}cm"
    
    parent_base_name_for_id = parent_base_name.lower().replace(' ', '_')
    child_external_id_name = f"product_template_{parent_base_name_for_id}_{grammage}gr_{int(cut_width*10)}x{int(cut_height*10)}cm".replace('.','')
    child_external_id = f"__export__.{child_external_id_name}"

    # --- PASO DE DEPURACIÓN: VERIFICAR CATEGORÍA ---
    categ_ext_id = '__export__.product_category_productos_intermedios_papel_cortado'
    try:
        print(f"  -> [DEBUG] Buscando categoría con ID externo: {categ_ext_id}")
        categ_record = odoo.env.ref(categ_ext_id)
        print(f"  -> [DEBUG] Encontrado: '{categ_record.display_name}', Modelo: '{categ_record._name}'")
        if categ_record._name != 'product.category':
            print(f"  -> ❌ ERROR: El ID externo apunta a un modelo incorrecto ({categ_record._name})!")
            return
        categ_id_val = categ_record.id
    except Exception as e:
        print(f"  -> ❌ ERROR: No se pudo encontrar la categoría con ID externo '{categ_ext_id}'. Error: {e}")
        return

    # 2. Verificar si el producto hijo ya existe
    try:
        child_template = odoo.env.ref(child_external_id)
        if child_template:
            print(f"    -> Producto hijo ya existe: {child_name} (ID: {child_template.id}) ")
            child_template_id = child_template.id
        else:
            raise Exception("No encontrado")
    except Exception:
        print(f"    -> Creando producto hijo: {child_name}")
        # 3. Crear el producto hijo si no existe
        child_vals = {
            'name': child_name,
            'type': 'product',
            'categ_id': categ_id_val,
            'purchase_ok': False,
            'sale_ok': False,
            'invoice_policy': 'order',
            'route_ids': [(6, 0, [odoo.env.ref('mrp.route_warehouse0_manufacture').id, odoo.env.ref('stock.route_warehouse0_mto').id])]
        }
        try:
            new_template_id = product_template_model.create(child_vals)
            odoo.env['ir.model.data'].create({
                'name': child_external_id_name,
                'module': '__export__',
                'model': 'product.template',
                'res_id': new_template_id,
            })
            child_template_id = new_template_id
            print(f"    -> Producto hijo CREADO con ID: {child_template_id}")
        except Exception as e:
            print(f"    -> ❌ Error al crear producto hijo en Odoo: {e}")
            return

    # 4. Verificar si la LdM ya existe
    bom_ids = bom_model.search([('product_tmpl_id', '=', child_template_id)])
    if bom_ids:
        print(f"    -> LdM para {child_name} ya existe.")
        return

    # 5. Crear la LdM con la operación directamente
    print(f"    -> Creando LdM con operación para: {child_name}")
    
    parent_product_variant_ids = odoo.env['product.product'].search([('product_tmpl_id', '=', parent_product_id)])
    if not parent_product_variant_ids:
        print(f"    -> ❌ Error: No se encontró una variante de producto para el pliego padre ID {parent_product_id}")
        return
    parent_product_variant_id = parent_product_variant_ids[0]

    try:
        workcenter_id = odoo.env.ref('__export__.mrp_workcenter_guillotina_principal_polar_mohr').id

        # 1. Preparar el PDF para la hoja de trabajo ANTES de crear la LdM.
        pdf_encoded_data = None
        p_w_mm = int(parent_paper_info['width'] * 10)
        p_h_mm = int(parent_paper_info['height'] * 10)
        c_w_mm = int(cut_width * 10)
        c_h_mm = int(cut_height * 10)
        pdf_filename = f"Corte_{p_w_mm}x{p_h_mm}_{c_w_mm}x{c_h_mm}.pdf"
        pdf_path = os.path.join('layouts_pdf', pdf_filename)

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                # Leemos y codificamos el PDF para el campo 'worksheet'
                pdf_encoded_data = base64.b64encode(pdf_file.read())
        else:
            print(f"    -> ⚠️ ADVERTENCIA: No se encontró el PDF para la hoja de trabajo: {pdf_path}")
        
        # 1. Configurar la operación para cálculo automático de tiempo.
        # Odoo calculará la duración basándose en los tiempos registrados para este centro.
        # El ciclo se medirá por cada 100 hojas.
        bom_vals = {
            'product_tmpl_id': child_template_id,
            'product_qty': pieces,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {
                    'product_id': parent_product_variant_id,
                    'product_qty': 1,
                })
            ],
            'operation_ids': [(0, 0, {
                'name': f"Corte en {pieces} partes",
                'workcenter_id': workcenter_id,
                'time_mode': 'auto',
                'time_mode_batch': 100,
                'sequence': 1,
                'worksheet_type': 'pdf',
                'worksheet': pdf_encoded_data.decode('ascii') if pdf_encoded_data else False,
            })]
        }
        
        new_bom_id = bom_model.create(bom_vals)
        print(f"    -> LdM CREADA con ID: {new_bom_id}")

        # 6. Adjuntar el PDF como un anexo (además de la hoja de trabajo)
        if pdf_encoded_data:
            # Adjuntar a la LdM (BoM)
            attachment_vals = {
                'name': pdf_filename,
                'datas': pdf_encoded_data.decode('ascii'),
                'res_model': 'mrp.bom',
                'res_id': new_bom_id,
                'type': 'binary',
            }
            attachment_model.create(attachment_vals)
            print(f"    -> PDF {pdf_filename} adjuntado a la LdM.")

    except Exception as e:
        print(f"    -> ❌ Error al crear LdM o adjuntar PDF: {e}")

def get_or_create_parent_paper_db(paper_info):
    """Obtiene o crea un registro para el papel padre en la DB de gestión."""
    with sqlite3.connect(DB_GESTION_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM papeles_padre WHERE external_id = ?", (paper_info['external_id'],))
        res = cursor.fetchone()
        if res:
            return res[0]
        else:
            cursor.execute("INSERT INTO papeles_padre (external_id, nombre_original) VALUES (?, ?)",
                           (paper_info['external_id'], paper_info['original_name']))
            return cursor.lastrowid

def check_child_exists_db(parent_db_id, cut_info):
    """Verifica si un hijo ya ha sido generado para un padre específico."""
    with sqlite3.connect(DB_GESTION_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hijos_generados WHERE papel_padre_id = ? AND corte_ancho = ? AND corte_alto = ?",
                       (parent_db_id, cut_info['ancho'], cut_info['alto']))
        return cursor.fetchone() is not None

def record_child_generation_db(parent_db_id, cut_info):
    """Registra que un producto hijo ha sido generado."""
    with sqlite3.connect(DB_GESTION_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO hijos_generados (papel_padre_id, corte_ancho, corte_alto, fecha_creacion) VALUES (?, ?, ?, ?)",
                           (parent_db_id, cut_info['ancho'], cut_info['alto'], datetime.now().isoformat()))
        except sqlite3.IntegrityError:
            # Ya existe, no hacer nada
            pass

def generate_csv_row(parent_paper_info, cut_info):
    """Genera un diccionario que representa una fila del CSV de importación."""
    grammage = parent_paper_info['grammage']
    cut_width = cut_info['ancho']
    cut_height = cut_info['alto']
    pieces = cut_info['piezas']

    # --- Nombres y IDs ---
    parent_base_name = parent_paper_info['original_name'].split(f" {grammage}gr")[0].strip()
    child_name = f"{parent_base_name} {grammage}gr {cut_width}x{cut_height}cm"
    
    # Limpieza de nombre para ID
    clean_parent_name = parent_base_name.lower().replace(' ', '_').replace('/', '_').replace(',', '')
    clean_cut_size = f"{int(cut_width*10)}x{int(cut_height*10)}cm".replace('.', '')

    # IDs de Producto
    child_tmpl_id_name = f"product_template_{clean_parent_name}_{grammage}gr_{clean_cut_size}"
    child_prod_id_name = f"product_product_{clean_parent_name}_{grammage}gr_{clean_cut_size}"
    child_tmpl_ext_id = f"__export__.{child_tmpl_id_name}"
    child_prod_ext_id = f"__export__.{child_prod_id_name}"

    # IDs de LdM
    bom_ref = f"Creacion de pliego {cut_width}x{cut_height}cm. desde {parent_paper_info['original_name']}"
    bom_id_name = f"mrp_bom_{clean_parent_name}_{grammage}gr_{clean_cut_size}"
    bom_ext_id = f"__export__.{bom_id_name}"

    # --- PDF ---
    pdf_encoded_data = ""
    p_w_mm = int(parent_paper_info['width'] * 10)
    p_h_mm = int(parent_paper_info['height'] * 10)
    c_w_mm = int(cut_width * 10)
    c_h_mm = int(cut_height * 10)
    pdf_filename = f"Corte_{p_w_mm}x{p_h_mm}_{c_w_mm}x{c_h_mm}.pdf"
    pdf_path = os.path.join('layouts_pdf', pdf_filename)
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as pdf_file:
            pdf_encoded_data = base64.b64encode(pdf_file.read()).decode('ascii')

    # --- Construcción de la fila del CSV ---
    row_data = {
        'Categoría del producto/ID externo': '__export__.product_category_productos_intermedios_papel_cortado',
        'Nombre': child_name,
        'Lista de materiales/Referencia': bom_ref,
        'Lista de materiales/Cantidad': pieces,
        'Lista de materiales / Líneas de la lista de materiales / Componente (no importar)': parent_paper_info['original_name'],
        'Lista de materiales/Operaciones/Operación': f"Corte en {pieces} partes",
        'Lista de materiales / Líneas de la lista de materiales / Cantidad': 1,
        'Categoría de la unidad de medida (no importar)': 'Hojas',
        'Unidad de medida (no importar)': 'Hoja',
        'UdM de compra (No importar)': 'Hoja',
        'Se puede comprar': 'FALSO',
        'Se puede vender': 'FALSO',
        'Product Type': 'Almacenable',
        'Política de facturación': 'Cantidades pedidas',
        'Lista de materiales/Operaciones/Cálculo de duración': 'Calcular según el tiempo registrado',
        'Lista de materiales/Operaciones/Con base en': 100,
        'Lista de materiales/Operaciones/PDF': '', # Dejado en blanco según ejemplo
        'Lista de materiales/Operaciones/Presentaciones de Google': '', # Dejado en blanco
        'Lista de materiales/Operaciones/Descripción': '', # Dejado en blanco
        'Lista de materiales/Tipo de lista de materiales': 'Fabricar este producto',
        'Etiquetas de la plantilla del producto': 'Pliego de impresión',
        'Rutas': 'Obtener Bajo Pedido (MTO),Fabricación',
        'Responsable': 'Andrea Fein',
        'Impuestos del cliente': 'IVA Ventas (22%)',
        'Ubicación de producción': 'Virtual Locations/Production',
        'Ubicación de inventario': 'Virtual Locations/Inventory adjustment',
        'Lista de materiales/Operaciones/Centro de trabajo (No importar)': 'Guillotina Principal Polar Mohr',
        'Id': child_tmpl_ext_id,
        'Producto/ID externo': child_prod_ext_id,
        'Lista de materiales/ID': bom_ext_id,
        'Unidad de medida/ID externo': '__export__.uom_uom_hojas_hoja',
        'UdM de compra/ID externo': '__export__.uom_uom_hojas_hoja',
        'Lista de materiales / Líneas de la lista de materiales / Componente / ID': parent_paper_info['external_id'].replace('product_template', 'product_product'),
        'Lista de materiales/Operaciones/Centro de trabajo/ID': '__export__.mrp_workcenter_guillotina_principal_polar_mohr',
        'Lista de materiales/Operaciones/Hoja de trabajo': 'PDF',
        'Lista de materiales/Operaciones/PDF': pdf_encoded_data
    }
    return row_data

def procesar_lotes_en_odoo(odoo, trabajos_a_procesar): # REESTRUCTURADO v2
    """
    Procesa la creación de productos y LdMs usando IDs externos para las LdMs para evitar duplicados.
    """
    if not trabajos_a_procesar:
        print("No hay nuevos trabajos para procesar en lote.")
        return

    print(f"\n--- ⚙️ Iniciando procesamiento en lote para {len(trabajos_a_procesar)} productos hijos ---")

    try:
        categ_intermedios_id = odoo.env.ref('__export__.product_category_productos_intermedios_papel_cortado').id
        mrp_route_manufacture_id = odoo.env.ref('mrp.route_warehouse0_manufacture').id
        stock_route_mto_id = odoo.env.ref('stock.route_warehouse0_mto').id
        workcenter_id = odoo.env.ref('__export__.mrp_workcenter_guillotina_principal_polar_mohr').id
    except Exception as e:
        print(f"❌ ERROR: No se pudieron obtener IDs de referencia de Odoo (categoría/rutas): {e}")
        return

    product_template_model = odoo.env['product.template']
    product_product_model = odoo.env['product.product']
    bom_model = odoo.env['mrp.bom']
    data_model = odoo.env['ir.model.data']

    # --- Preparación de Datos Locales ---
    print("  - Preparando datos locales de todos los posibles hijos...")
    productos_hijos_map = {}
    child_prod_ext_ids_a_buscar = []
    bom_ext_ids_a_buscar = []

    for trabajo in trabajos_a_procesar:
        parent_info = trabajo['parent_paper_info']
        cut_info = trabajo['cut_info']
        grammage = parent_info['grammage']
        child_name = f"{parent_info['original_name'].split(f' {grammage}gr')[0].strip()} {grammage}gr {cut_info['ancho']}x{cut_info['alto']}cm"
        
        # --- Generación de IDs Externos para Producto y LdM ---
        clean_parent_name = parent_info['original_name'].split(f' {grammage}gr')[0].strip().lower().replace(' ', '_').replace('/', '_').replace(',', '')
        clean_cut_size = f"{int(cut_info['ancho']*10)}x{int(cut_info['alto']*10)}cm".replace('.', '')
        
        # ID Externo del Producto Hijo
        child_prod_ext_id_name = f"product_template_{clean_parent_name}_{grammage}gr_{clean_cut_size}"
        child_prod_ext_id_full = f"__export__.{child_prod_ext_id_name}"
        
        # ID Externo de la LdM (según nuevo formato)
        clean_parent_name_for_bom = parent_info['original_name'].lower().replace(' ', '_').replace('/', '_').replace(',', '')
        bom_ext_id_name = f"mrp_bom_creacion_de_pliego_{clean_cut_size}_desde_{clean_parent_name_for_bom}"
        bom_ext_id_full = f"__export__.{bom_ext_id_name}"

        child_prod_ext_ids_a_buscar.append(child_prod_ext_id_full)
        bom_ext_ids_a_buscar.append(bom_ext_id_full)

        productos_hijos_map[child_prod_ext_id_full] = {
            'vals': {
                'name': child_name,
                'type': 'product',
                'categ_id': categ_intermedios_id,
                'purchase_ok': False, 'sale_ok': False, 'invoice_policy': 'order',
                'route_ids': [(6, 0, [mrp_route_manufacture_id, stock_route_mto_id])]
            },
            'ext_id_name': child_prod_ext_id_name,
            'bom_ext_id_name': bom_ext_id_name,
            'bom_ext_id_full': bom_ext_id_full,
            'parent_template_id': trabajo['parent_template_id'],
            'cut_info': cut_info,
            'trabajo_original': trabajo
        }

    # --- Consulta 1: Verificar Productos Hijos Existentes ---
    print("  1. Consultando API Odoo para verificar la existencia de productos hijos...")
    child_prod_names_to_check = [ext_id.split('.')[1] for ext_id in child_prod_ext_ids_a_buscar]
    existing_child_prods_data = data_model.search_read(
        [('module', '=', '__export__'), ('name', 'in', child_prod_names_to_check)],
        ['name', 'res_id']
    )
    mapa_child_prod_name_to_res_id = {d['name']: d['res_id'] for d in existing_child_prods_data}

    hijos_existentes_map = {}
    hijos_faltantes_map = {}
    for ext_id, data in productos_hijos_map.items():
        if data['ext_id_name'] in mapa_child_prod_name_to_res_id:
            data['res_id'] = mapa_child_prod_name_to_res_id[data['ext_id_name']]
            hijos_existentes_map[ext_id] = data
        else:
            hijos_faltantes_map[ext_id] = data
    print(f"     -> {len(hijos_existentes_map)} productos hijos ya existen. {len(hijos_faltantes_map)} son nuevos.")

    # --- Consulta 2: Verificar LdMs Existentes por ID Externo ---
    print("  2. Consultando API Odoo para verificar la existencia de LdMs...")
    bom_names_to_check = [ext_id.split('.')[1] for ext_id in bom_ext_ids_a_buscar]
    existing_boms_data = data_model.search_read(
        [('module', '=', '__export__'), ('model', '=', 'mrp.bom'), ('name', 'in', bom_names_to_check)],
        ['name']
    )
    existing_bom_names = {d['name'] for d in existing_boms_data}
    print(f"     -> {len(existing_bom_names)} LdMs ya existen.")

    # --- Crear Productos Hijos Faltantes ---
    if hijos_faltantes_map:
        print("  3. Creando productos hijos faltantes...")
        print("     - Creación 1 (productos) contra la API Odoo...")
        productos_faltantes_vals = [data['vals'] for data in hijos_faltantes_map.values()]
        nuevos_productos_ids = product_template_model.create(productos_faltantes_vals)
        
        data_vals_lote = []
        for i, (ext_id, data) in enumerate(hijos_faltantes_map.items()):
            data_vals_lote.append({'name': data['ext_id_name'], 'module': '__export__', 'model': 'product.template', 'res_id': nuevos_productos_ids[i]})
            hijos_faltantes_map[ext_id]['res_id'] = nuevos_productos_ids[i]
        data_model.create(data_vals_lote)
        print("     -> ✅ Productos y IDs externos creados.")

    # --- Crear LdMs Faltantes (para TODOS los hijos, existentes y nuevos) ---
    print("  4. Preparando y creando LdMs faltantes...")
    all_parent_tmpl_ids = list(set(d['parent_template_id'] for d in productos_hijos_map.values()))
    print("     - Consultando API Odoo para obtener las variantes de los pliegos padre...")
    parent_variants_data = product_product_model.search_read(
        [('product_tmpl_id', 'in', all_parent_tmpl_ids)],
        ['product_tmpl_id']
    )
    mapa_parent_tmpl_a_variant = {d['product_tmpl_id'][0]: d['id'] for d in parent_variants_data}

    ldms_a_crear_vals = []
    for ext_id, data in productos_hijos_map.items():
        # Si el ID externo de la LdM ya existe, la omitimos.
        if data['bom_ext_id_name'] in existing_bom_names:
            continue

        child_tmpl_id = data.get('res_id')
        parent_variant_id = mapa_parent_tmpl_a_variant.get(data['parent_template_id'])
        if not child_tmpl_id or not parent_variant_id:
            print(f"     -> ⚠️ Omitiendo LdM para '{data['vals']['name']}' por falta de ID de hijo o padre.")
            continue

        bom_vals = {
            'product_tmpl_id': child_tmpl_id,
            'product_qty': data['cut_info']['piezas'],
            'type': 'normal',
            'bom_line_ids': [(0, 0, {'product_id': parent_variant_id, 'product_qty': 1})],
            'operation_ids': [(0, 0, {'name': f"Corte en {data['cut_info']['piezas']} partes", 'workcenter_id': workcenter_id, 'time_mode': 'auto', 'time_mode_batch': 100})],
        }
        ldms_a_crear_vals.append({'vals': bom_vals, 'trabajo': data['trabajo_original'], 'bom_ext_id_name': data['bom_ext_id_name']})

    if ldms_a_crear_vals:
        print(f"     - Creando {len(ldms_a_crear_vals)} LdMs nuevas en lote...")
        print("     - Creación 2 (LdMs) contra la API Odoo...")
        
        # Crear las LdMs
        nuevas_ldms_ids = bom_model.create([item['vals'] for item in ldms_a_crear_vals])
        
        # Crear los ir.model.data para las nuevas LdMs
        data_vals_ldm_lote = []
        for i, item in enumerate(ldms_a_crear_vals):
            data_vals_ldm_lote.append({
                'name': item['bom_ext_id_name'],
                'module': '__export__',
                'model': 'mrp.bom',
                'res_id': nuevas_ldms_ids[i]
            })
        data_model.create(data_vals_ldm_lote)
        print("     -> ✅ LdMs y sus IDs externos creados.")

        # Registrar en la DB de gestión
        print("     -> Registrando LdMs creadas en la base de datos de gestión...")
        for item in ldms_a_crear_vals:
            trabajo = item['trabajo']
            record_child_generation_db(trabajo['parent_db_id'], trabajo['cut_info'])

    # Registrar los hijos que ya existían y cuya LdM ya existía
    print("  - Registrando hijos y LdMs preexistentes en la base de datos de gestión (para consistencia)...")
    for ext_id, data in productos_hijos_map.items():
        if data['bom_ext_id_name'] in existing_bom_names:
            record_child_generation_db(data['trabajo_original']['parent_db_id'], data['trabajo_original']['cut_info'])

    print("\n--- ✅ Fin del procesamiento en lote ---")

def main(args):
    """Función principal del script que maneja diferentes modos de ejecución."""
    odoo = conectar_odoo()
    if not odoo:
        return

    # --- MODO: Adjuntar PDFs ---
    if args.adjuntar_pdfs or args.forzar_adjuntar_pdfs:
        adjuntar_pdfs_faltantes(odoo, forzar=args.forzar_adjuntar_pdfs)
        print("\nProceso de adjuntar PDFs finalizado.")
        return

    # --- Lógica original para generar productos ---

    # Inicializar la base de datos de gestión
    inicializar_db_gestion()

    # Crear el directorio de salida para los CSV si se usa ese modo
    if args.csv:
        CSV_OUTPUT_DIR = "csv_productos_hijos"
        os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)

    try:
        with open('materia_prima_ahuesado.csv', mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile, delimiter=',')
            headers = next(reader)
            
            for row in reader:
                if not row or len(row) < len(headers):
                    continue

                paper_info = get_paper_info(row, headers)
                if paper_info:
                    print(f"\nProcesando papel: {paper_info['original_name']}")
                    
                    # Listas para acumular datos POR CADA PAPEL PADRE
                    if args.csv:
                        child_products_for_this_parent = []
                    
                    if args.procesar_lotes:
                        trabajos_para_lote_del_padre = []
                    
                    parent_template_id = ensure_product_exists(odoo, row, headers)
                    if not parent_template_id:
                        continue

                    # Obtener el ID del papel padre en nuestra DB de gestión
                    parent_db_id = get_or_create_parent_paper_db(paper_info)

                    pliego_cm = (paper_info['width'], paper_info['height'])
                    minimo_cm = (21.0, 30.0)
                    maximo_cm = pliego_cm
                    incremento = 0.1

                    analisis_id_tuple = check_cache(DB_PATH, pliego_cm, minimo_cm, maximo_cm, incremento)
                    
                    if not analisis_id_tuple:
                        run_optimizer(pliego_cm)
                        analisis_id_tuple = check_cache(DB_PATH, pliego_cm, minimo_cm, maximo_cm, incremento)
                        if not analisis_id_tuple:
                            print(f"  -> ❌ Error: No se pudo encontrar el análisis para {pliego_cm} después de ejecutar el optimizador.")
                            continue
                    
                    analisis_id = analisis_id_tuple[0]
                    print(f"  -> Análisis encontrado con ID: {analisis_id}")
                    optimal_cuts = fetch_results(DB_PATH, analisis_id)
                    print(f"  -> Se encontraron {len(optimal_cuts)} cortes óptimos.")

                    #print("\n--- MODO DE PRUEBA: Procesando solo el primer corte óptimo encontrado. ---")
                    for cut in optimal_cuts:

                        # --- LÓGICA CONDICIONAL: CSV o API ---
                        if args.csv:
                            # Modo CSV: Siempre genera la fila, sin verificar ni registrar en la DB de gestión.
                            csv_row = generate_csv_row(paper_info, cut)
                            child_products_for_this_parent.append(csv_row)
                        else:
                            # --- LÓGICA CONDICIONAL: LOTE o INDIVIDUAL ---
                            if args.procesar_lotes:
                                # Modo Lote: Acumula el trabajo para procesarlo al final de este papel padre.
                                if not args.forzar_regeneracion and check_child_exists_db(parent_db_id, cut):
                                    print(f"    -> (Lote) Omitiendo corte {cut['ancho']}x{cut['alto']}cm. Ya fue generado.")
                                    continue
                                trabajos_para_lote_del_padre.append({'parent_template_id': parent_template_id, 'parent_paper_info': paper_info, 'cut_info': cut, 'parent_db_id': parent_db_id})
                            else:
                                # Modo Individual (original): Verifica y crea uno por uno.
                                if not args.forzar_regeneracion and check_child_exists_db(parent_db_id, cut):
                                    print(f"    -> Omitiendo corte {cut['ancho']}x{cut['alto']}cm. Ya fue generado previamente.")
                                    continue
                                create_child_product_and_bom(odoo, parent_template_id, paper_info, cut)
                                record_child_generation_db(parent_db_id, cut)
                    
                    # Si se generaron filas para el CSV, se escribe el archivo.
                    if args.csv and child_products_for_this_parent:
                        csv_filename = f"productos_hijos_{paper_info['original_name'].lower().replace(' ', '_').replace('/', '_')}.csv"
                        csv_filepath = os.path.join(CSV_OUTPUT_DIR, csv_filename)
                        output_headers = list(child_products_for_this_parent[0].keys())
                        with open(csv_filepath, mode='w', encoding='utf-8', newline='') as outfile:
                            writer = csv.DictWriter(outfile, fieldnames=output_headers)
                            writer.writeheader()
                            writer.writerows(child_products_for_this_parent)
                        print(f"  -> ✅ Generado archivo CSV: {csv_filepath}")

                    # Al final de procesar un papel padre, si estamos en modo lote, enviamos su lote.
                    if args.procesar_lotes and trabajos_para_lote_del_padre:
                        procesar_lotes_en_odoo(odoo, trabajos_para_lote_del_padre)

    except FileNotFoundError:
        print("Error: No se encontró el archivo 'materia_prima_ahuesado.csv'.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Genera productos hijos y LdMs en Odoo a partir de pliegos de papel.")
    parser.add_argument('--forzar-regeneracion', action='store_true', help="Ignora la caché y vuelve a generar todos los productos hijos y LdMs.")
    parser.add_argument('--csv', action='store_true', help="Genera archivos CSV para importación en lugar de crear los productos por API.")
    parser.add_argument('--procesar-lotes', action='store_true', help="Procesa la creación de productos y LdMs en lotes para mayor eficiencia (modo API).")
    parser.add_argument('--adjuntar-pdfs', action='store_true', help="Busca LdMs sin hoja de trabajo y adjunta el PDF correspondiente.")
    parser.add_argument('--forzar-adjuntar-pdfs', action='store_true', help="Fuerza la actualización de PDFs en todas las operaciones de corte, ignorando si ya existen.")
    args = parser.parse_args()
    main(args)
