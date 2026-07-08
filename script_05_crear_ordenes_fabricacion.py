# -*- coding: utf-8 -*-
"""
Script 5: Creador de Órdenes de Fabricación (OF) en Odoo.

- Lee la DB local en busca de trabajos que ya tienen pickings creados pero no una OF.
- Para cada línea de trabajo, busca la Lista de Materiales (LdM) correspondiente en Odoo.
- Si la LdM existe, crea y confirma la Orden de Fabricación, asegurando el enlace con
  el Pedido de Venta a través del 'procurement_group_id'.
- Actualiza la DB local con el ID de la nueva OF y el estado de fabricación.
- Notifica por email si no se encuentra una LdM para un producto.
"""

import logging
# Inicializar logger
_logger = logging.getLogger(__name__)

from datetime import datetime
import math
import re
import os # Importar módulo os para operaciones de sistema de archivos
import fitz # Importar PyMuPDF para procesamiento de PDF
import base64 # Importar base64 para codificar imágenes
import io # Importar módulo io para manejar streams de bytes en memoria

# Importar módulos comunes de la V2.0
from common import db_conn, odoo_conn, mapeos
from common.notificador import enviar_email
from common.bmg_estados_mapeo import MAPEO_ESTADOS_BMG


def crear_o_buscar_producto(odoo, name, default_code, es_componente=True):
    """
    Crea un producto si no existe, o lo devuelve si ya existe.
    Esta función es robusta frente a 'race conditions' durante la creación.
    """
    Product = odoo.env['product.product']
    product_ids = Product.search([('default_code', '=', default_code)])
    
    target_route_names = []
    if es_componente:
        target_route_names = ['Fabricación', 'Obtener Bajo Pedido (MTO)']
    
    target_route_ids = odoo.env['stock.route'].search([
        ('name', 'in', target_route_names)
    ])

    if product_ids:
        product_id = product_ids[0]
        _logger.info(f"    -> Producto intermedio encontrado: \"{name}\" (ID: {product_id})")
        
        current_product = Product.browse(product_id)
        current_route_ids = [r.id for r in current_product.route_ids] if current_product.route_ids else []

        if set(target_route_ids) != set(current_route_ids):
            _logger.info(f"    -> Actualizando rutas para el producto existente: \"{name}\"")
            Product.write([product_id], {'route_ids': [(6, 0, target_route_ids)]})
        
        return product_id
    
    # Si no se encontró, intentar crear
    _logger.info(f"    -> Creando producto intermedio: \"{name}\" con código: {default_code}")
    product_vals = {
        'name': name,
        'default_code': default_code,
        'type': 'product',
        'categ_id': 1,
        'purchase_ok': False,
        'sale_ok': False,
    }
    if es_componente:
        product_vals['route_ids'] = [(6, 0, target_route_ids)]

    try:
        new_product_id = Product.create(product_vals)
        _logger.info(f"    -> Producto '{name}' creado con éxito (ID: {new_product_id}).")
        return new_product_id
    except Exception as e:
        # Si la creación falla, puede ser por una 'race condition' (otro proceso lo creó justo ahora).
        # El mensaje de error de Odoo para violación de unicidad suele contener 'unique'.
        if 'unique' in str(e):
            _logger.warning(f"    -> La creación del producto falló (posible 'race condition'). Re-buscando producto con código '{default_code}'.")
            # Esperar un instante y re-buscar para dar tiempo a la otra transacción a completarse.
            import time
            time.sleep(1)
            product_ids = Product.search([('default_code', '=', default_code)])
            if product_ids:
                _logger.info("    -> Producto encontrado en el segundo intento.")
                # Re-llamamos a la función para asegurar que las rutas se actualicen si es necesario.
                return crear_o_buscar_producto(odoo, name, default_code, es_componente)
            else:
                _logger.error(f"    -> ERROR CRÍTICO: Falló la creación por unicidad, pero el producto '{default_code}' no se encuentra.")
                raise e # Re-lanzar el error original porque la situación es anómala.
        else:
            # Si el error es por otra causa, simplemente lo re-lanzamos.
            _logger.error(f"    -> ERROR INESPERADO al crear producto '{default_code}': {e}")
            raise e

def extract_image_from_pdf(pdf_path):
    """
    Extrae la primera página de un PDF como imagen PNG y la devuelve codificada en Base64.
    Utiliza un archivo temporal para compatibilidad con versiones antiguas de PyMuPDF.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        _logger.warning(f"  -> ADVERTENCIA: Ruta de archivo de tapa no válida o no existe: {pdf_path}")
        return None
    
    # Importar tempfile aquí para que solo se importe si es necesario, 
    # y para evitar que el usuario lo vea si no se ha usado antes.
    import tempfile 

    temp_file = None
    try:
        with fitz.open(pdf_path) as doc:
            if doc.page_count > 0:
                page = doc.load_page(0)  # Cargar la primera página
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0)) 
                
                # Crear un archivo temporal para guardar la imagen
                # Usamos suffix='.png' para indicar el tipo de archivo
                # delete=False para que no se borre automáticamente al cerrar,
                # y lo borramos nosotros manualmente al final.
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_output:
                    temp_file = temp_output.name # Guardamos el nombre del archivo temporal
                    pix.save(temp_file) # Guardar el pixmap en el archivo temporal como PNG
                
                # Leer los datos del archivo temporal
                with open(temp_file, 'rb') as f:
                    img_data = f.read()

                return base64.b64encode(img_data).decode('ascii')
        _logger.warning(f"  -> ADVERTENCIA: El PDF de la tapa '{pdf_path}' está vacío o corrupto.")
        return None
    except Exception as e:
        _logger.error(f"  -> ERROR al extraer imagen de la tapa del PDF '{pdf_path}': {e}")
        return None
    finally:
        # Asegurarse de que el archivo temporal sea eliminado
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
            _logger.info(f"  -> Archivo temporal '{temp_file}' eliminado.")

def crear_ldm(odoo, product_id, components, operations, trabajo):
    """
    Crea o actualiza una Lista de Materiales (LdM) para una variante de producto específica.
    Si la LdM ya existe, actualiza sus componentes y operaciones.
    """
    MrpBom = odoo.env['mrp.bom']
    
    # La LdM debe estar asociada a la variante de producto específica
    existing_boms = MrpBom.search([('product_id', '=', product_id)])
    
    # Preparar los datos de los componentes y operaciones
    bom_line_vals = []
    for comp in components:
        bom_line_vals.append((0, 0, {
            'product_id': comp['product_id'],
            'product_qty': comp['quantity']
        }))

    operation_vals = []
    sequence = 10
    # The 'channel' variable is not used after this point, so it's safe to keep it
    # but the crucial part is how 'es_edist' is determined based on 'order_type'.
    # channel = trabajo.get('channel', '')
    es_edist = trabajo.get('order_type') == mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1
    _logger.info(f"DEBUG: Pedido {trabajo.get('order_code')}-{trabajo.get('line_number')}, order_type: '{trabajo.get('order_type')}', es_edist: {es_edist}")
    for op in operations:
        bmg_op_key = op.get('bmg_op_key')
        bmg_config = MAPEO_ESTADOS_BMG.get(bmg_op_key, {})
        wip_states = bmg_config.get('estado_en_progreso', {}) or {}
        done_states = bmg_config.get('estado_completado', {}) or {}
        wip_id = wip_states.get('eDist') if es_edist else wip_states.get('POD')
        done_id = done_states.get('eDist') if es_edist else done_states.get('POD')
        
        _logger.info(f"DEBUG: Operación '{op.get('name')}' (key: {bmg_op_key}): wip_id={wip_id}, done_id={done_id} (es_edist={es_edist})")
        operation_data = {
            'name': op['name'],
            'workcenter_id': odoo.env.ref(op['workcenter_ext_id']).id,
            'time_cycle': 1,
            'sequence': sequence,
            'x_bmg_estado_wip_id': wip_id if wip_id is not None else False,
            'x_bmg_estado_done_id': done_id if done_id is not None else False,
        }
        operation_vals.append((0, 0, operation_data))
        sequence += 10

    if existing_boms:
        bom_id = existing_boms[0]
        _logger.info(f"    -> LdM para el producto variante ID {product_id} ya existe (ID: {bom_id}). Actualizando...")
        
        # --- COMPONENTES: se pueden borrar y recrear sin problema ---
        MrpBom.write([bom_id], {
            'bom_line_ids': [(5, 0, 0)],
        })
        MrpBom.write([bom_id], {
            'bom_line_ids': bom_line_vals,
        })
        
        # --- OPERACIONES: actualizar IN-PLACE para NO romper workorders existentes ---
        # Las operaciones (mrp.routing.workcenter) son referenciadas por workorders
        # a traves de operation_id. Si las borramos con (5,0,0), los workorders
        # pierden x_bmg_estado_wip_id y x_bmg_estado_done_id.
        MrpRoutingWC = odoo.env['mrp.routing.workcenter']

        # IMPORTANTE: usamos search_read en vez de .browse() + iterar
        # bom_record.operation_ids. Ese one2many devuelve objetos ya
        # "browseados" (no IDs), y volver a pasarlos a .browse() (o guardarlos
        # tal cual en un comando de escritura) rompe con
        # 'Object of type mrp_routing_workcenter is not JSON serializable'.
        bom_data = MrpBom.search_read([('id', '=', bom_id)], ['id', 'operation_ids'])
        existing_op_ids = bom_data[0].get('operation_ids') or [] if bom_data else []
        _logger.info(f"      [DEBUG] bom_data={bom_data!r}")
        _logger.info(f"      [DEBUG] existing_op_ids={existing_op_ids!r} tipo={type(existing_op_ids)} "
                     f"tipos_elementos={[type(x) for x in existing_op_ids]}")

        # Crear un mapa de operaciones existentes por nombre
        existing_ops_by_name = {}
        if existing_op_ids:
            op_rows = MrpRoutingWC.search_read(
                [('id', 'in', existing_op_ids)],
                ['id', 'name']
            )
            _logger.info(f"      [DEBUG] op_rows={op_rows!r}")
            for op_row in op_rows:
                existing_ops_by_name[op_row['name']] = op_row['id']
            _logger.info(f"      [DEBUG] existing_ops_by_name={existing_ops_by_name!r} "
                         f"tipos_valores={[type(v) for v in existing_ops_by_name.values()]}")
        
        # Determinar qué operaciones necesitan update, crear o eliminar
        new_op_names = set()
        ops_cmds = []
        for _, _, op_data in operation_vals:
            op_name = op_data['name']
            new_op_names.add(op_name)
            
            if op_name in existing_ops_by_name:
                # Actualizar la operación existente in-place (preserva el ID)
                ops_cmds.append((1, existing_ops_by_name[op_name], op_data))
                _logger.info(f"      -> Actualizando operación existente '{op_name}' (ID: {existing_ops_by_name[op_name]})")
            else:
                # Crear nueva operación
                ops_cmds.append((0, 0, op_data))
                _logger.info(f"      -> Creando nueva operación '{op_name}'")
        
        # Eliminar operaciones que ya no son necesarias (solo si no están en la nueva lista)
        for old_name, old_id in existing_ops_by_name.items():
            if old_name not in new_op_names:
                ops_cmds.append((2, old_id, 0))
                _logger.info(f"      -> Eliminando operación obsoleta '{old_name}' (ID: {old_id})")
        
        if ops_cmds:
            _logger.info(f"      [DEBUG] ops_cmds antes de escribir (tipos): "
                         f"{[(c[0], type(c[1]).__name__, c[1]) for c in ops_cmds]}")
            try:
                MrpBom.write([bom_id], {'operation_ids': ops_cmds})
            except Exception as e_write:
                _logger.error(f"      [DEBUG] FALLO el write de operation_ids. "
                              f"ops_cmds completo: {ops_cmds!r}")
                raise
        
        _logger.info(f"    -> ✅ LdM ID {bom_id} actualizada (componentes recreados, operaciones actualizadas in-place).")
        return

    # Si no existe, la creamos
    product_template_id = odoo.env['product.product'].browse(product_id).product_tmpl_id.id
    _logger.info(f"    -> Creando nueva LdM para el producto variante ID {product_id}")

    bom_vals = {
        'product_id': product_id,
        'product_tmpl_id': product_template_id,
        'product_qty': 1.0,
        'type': 'normal',
        'bom_line_ids': bom_line_vals,
        'operation_ids': operation_vals
    }
    
    MrpBom.create(bom_vals)
    _logger.info(f"    -> ✅ Nueva LdM creada.")


def run():
    """
    Ejecuta el proceso de creación de Órdenes de Fabricación.
    """
    if not mapeos.PRODUCCION_ACTIVADA:
        _logger.info("Script 05: Creación de Órdenes de Fabricación OMITIDA (Toggle desactivado en mapeos.py).")
        return

    _logger.info(f"--- Iniciando Script 5: Creación de Órdenes de Fabricación --- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    conn = db_conn.conectar_db()
    if not conn:
        asunto = "Error Crítico en Script 05: Conexión a DB local fallida"
        cuerpo = "El Script 05 no pudo establecer conexión con la base de datos local. Revise la configuración."
        enviar_email(asunto, cuerpo)
        return

    cursor = conn.cursor()
    # Construir la lista de IDs de estados no confirmables para OF
    ids_no_of = [id for id in mapeos.ESTADOS_NO_CONFIRMABLES_PARA_OF if id is not None]
    placeholders_no_of = ', '.join('?' for _ in ids_no_of)

    cursor.execute(f"""
        SELECT * FROM trabajos 
        WHERE odoo_pickings_data_json IS NOT NULL
        AND odoo_pickings_data_json != ''
        AND odoo_pickings_data_json != '[]'
        AND odoo_mrp_order_id IS NULL
        AND estado_fabricacion != '{mapeos.LOCAL_DB_STATUS_OF_CREADA}'
        AND estado_tapa_produccion = '{mapeos.LOCAL_DB_STATUS_TAPA_GENERADO}'
        AND estado_interior_produccion = '{mapeos.LOCAL_DB_STATUS_INTERIOR_GENERADO}'
        AND (line_status_id IS NULL OR line_status_id NOT IN ({placeholders_no_of}))
    """, ids_no_of)
    trabajos_a_procesar = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not trabajos_a_procesar:
        _logger.info("No hay trabajos nuevos para crear Órdenes de Fabricación.")
        return

    _logger.info(f"Se encontraron {len(trabajos_a_procesar)} trabajos para procesar.")
    
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        asunto = "Error Crítico en Script 05: Conexión a Odoo fallida"
        cuerpo = "El Script 05 no pudo establecer conexión con Odoo. Revise la configuración."
        enviar_email(asunto, cuerpo)
        return

    mrp_production_model = odoo_api.env['mrp.production']
    mrp_bom_model = odoo_api.env['mrp.bom']
    so_model = odoo_api.env['sale.order']
    procurement_group_model = odoo_api.env['procurement.group']

    for trabajo in trabajos_a_procesar:
        order_code = trabajo['order_code']
        line_number = trabajo['line_number']
        
        _logger.info(f"\n--- 🏭 Procesando trabajo: {order_code}-{line_number} ({trabajo['title']}) ---")
        
        # <<< INICIO: Omitir OF para trabajos de producción externa >>>
        printing_facility = trabajo.get('printing_facility', '').upper()
        if printing_facility and printing_facility != mapeos.BMG_PUBLISHER_FACILITY_LAD:
            _logger.info(f"    -> ℹ️ Omitiendo creación de OF: El trabajo es para una filial externa ('{printing_facility}').")
            continue
        # <<< FIN: Omitir OF para trabajos de producción externa >>>

        # <<< FIN: Omitir OF para trabajos de producción externa >>>

        try:
            # 1. OBTENER PRODUCTO FINAL Y DETERMINAR FLUJO
            libro_product_id = trabajo.get('odoo_product_variant_id')
            if not libro_product_id:
                _logger.error("    ❌ Error: El trabajo no tiene un 'odoo_product_variant_id'. No se puede continuar.")
                continue

            has_color_insert = trabajo.get('color_insert') == 'YES' and int(trabajo.get('color_pages', 0)) > 0
            interior_final_product_id = None

            # 2. PROCESAR TAPA
            _logger.info("  - Preparando LdM para la TAPA...")
            tapa_product_name = f"[TAPA] {trabajo['title']}"
            tapa_default_code = f"COMP-TAPA-{trabajo['order_code']}-{trabajo['line_number']}"
            tapa_product_id = crear_o_buscar_producto(odoo_api, tapa_product_name, tapa_default_code)

            tapa_components = []
            tamaño_papel_tapa = trabajo.get('papel_tapa_size')
            if not tamaño_papel_tapa:
                _logger.error(f"    ❌ Error: No se pudo determinar el tamaño de papel de tapa desde el trabajo.")
                continue

            try:
                ancho, alto = tamaño_papel_tapa.split('x')
                tamaño_formateado = f"{float(ancho):.1f}x{float(alto):.1f}"
            except ValueError:
                tamaño_formateado = tamaño_papel_tapa

            cartulina_product_name = f"Papel Cartulina CMPC 250gr {tamaño_formateado}cm"
            _logger.info(f"    -> Buscando dinámicamente el producto de tapa: \"{cartulina_product_name}\"")
            cartulina_product_ids = odoo_api.env['product.product'].search([('name', '=', cartulina_product_name)])
            
            if not cartulina_product_ids:
                _logger.error(f"    ❌ Error: No se encontró el producto de cartulina '{cartulina_product_name}' en Odoo.")
                continue
                
            cartulina_product_id = cartulina_product_ids[0]
            tapa_components.append({'product_id': cartulina_product_id, 'quantity': 1})
            
            tapa_operations = [
                {'name': 'Imprimir Tapa', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_7200'], 'bmg_op_key': 'IMPRIMIR_TAPA'},
                {'name': 'Guillotinar Tapa', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['GUILLOTINA'], 'bmg_op_key': 'GUILLOTINAR_TAPA'},
            ]
            
            laminado_api = trabajo.get('laminate')
            laminado_nombre = mapeos.MAPEO_LAMINADO.get(laminado_api, '').upper()
            
            def agregar_componente_laminado(nombre_laminado):
                if nombre_laminado in mapeos.MAPEO_LAMINADO_PRODUCTOS_ODOO:
                    laminado_ext_id = mapeos.MAPEO_LAMINADO_PRODUCTOS_ODOO[nombre_laminado]
                    laminado_template_id = odoo_api.env.ref(laminado_ext_id).id
                    variant_ids = odoo_api.env['product.product'].search([('product_tmpl_id', '=', laminado_template_id)])
                    if not variant_ids:
                        _logger.warning(f"    ⚠️ Advertencia: No se encontró una variante de producto para la plantilla de laminado ID {laminado_template_id}")
                        return
                    laminado_product_id = variant_ids[0]
                    largo_tapa_cm = float(tamaño_papel_tapa.split('x')[1])
                    tapa_components.append({'product_id': laminado_product_id, 'quantity': largo_tapa_cm / 100})
                    if not any(op['name'] == 'Laminar' for op in tapa_operations):
                        tapa_operations.insert(1, {'name': 'Laminar', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['LAMINADORA'], 'bmg_op_key': 'LAMINAR_TAPA'})
                else:
                    _logger.warning(f"    ⚠️ Advertencia: No se encontró el ID externo para el componente de laminado '{nombre_laminado}'")

            def agregar_operacion_barniz():
                if not any(op['name'] == 'Barnizar' for op in tapa_operations):
                    tapa_operations.insert(-1, {'name': 'Barnizar', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_7200'], 'bmg_op_key': None})

            if laminado_nombre == 'LAMINADO UV':
                _logger.info("    -> Lógica LAMINADO UV: Componente 'Laminado Mate' + Operación 'Barnizar'")
                agregar_componente_laminado('LAMINADO MATE')
                agregar_operacion_barniz()
            elif laminado_nombre in ['BARNIZADO', 'BARNIZ BRILLO A REGISTRO']:
                _logger.info(f"    -> Lógica {laminado_nombre}: Solo Operación 'Barnizar'")
                agregar_operacion_barniz()
            elif laminado_nombre:
                _logger.info(f"    -> Lógica {laminado_nombre}: Solo Componente de Laminado")
                agregar_componente_laminado(laminado_nombre)
            
            crear_ldm(odoo_api, tapa_product_id, tapa_components, tapa_operations, trabajo)

            # 3. PROCESAR INTERIOR(ES)
            layout = trabajo.get('interior_layout')
            papel_folder = trabajo.get('interior_papel_folder')
            if not layout or not papel_folder:
                _logger.error(f"    ❌ Error: No se encontraron datos de layout o papel de interior en el trabajo.")
                continue
            
            pages_per_sheet = 4 if layout == '2up' else 2
            
            # Determinar el tipo de libro
            try:
                bw_pages = int(trabajo.get('bw_pages') or 0)
            except (ValueError, TypeError):
                bw_pages = 0
            
            try:
                color_pages = int(trabajo.get('color_pages') or 0)
            except (ValueError, TypeError):
                color_pages = 0

            es_mixto = has_color_insert and bw_pages > 0
            es_solo_color = has_color_insert and bw_pages == 0
            es_solo_byn = not has_color_insert and bw_pages > 0

            if es_solo_byn:
                _logger.info("  - Preparando LdM para el INTERIOR (100% ByN)...")
                interior_product_name = f"[INTERIOR] {trabajo['title']}"
                interior_default_code = f"COMP-INT-{trabajo['order_code']}-{trabajo['line_number']}"
                interior_final_product_id = crear_o_buscar_producto(odoo_api, interior_product_name, interior_default_code)

                papel_code_api = trabajo.get('bw_paper_type')
                papel_nombre_completo = mapeos.MAPEO_NOMBRES_PAPEL.get(papel_code_api, "")
                if not papel_nombre_completo:
                    _logger.error(f"    ❌ Error: No se encontró mapeo para el papel ByN '{papel_code_api}'.")
                    continue
                
                grammage_match = re.search(r'(\d+)', papel_nombre_completo)
                if not grammage_match:
                    _logger.error(f"    ❌ Error: No se pudo extraer el gramaje de '{papel_nombre_completo}'")
                    continue
                grammage = grammage_match.group(1)
                nombre_base_papel = papel_nombre_completo.replace(grammage, '').strip()

                try:
                    ancho, alto = papel_folder.split('x')
                    dimensiones_formateadas = f"{float(ancho):.1f}x{float(alto):.1f}"
                except ValueError:
                    dimensiones_formateadas = papel_folder

                papel_cortado_name = f"Papel {nombre_base_papel} {grammage}gr {dimensiones_formateadas}cm"
                
                papel_cortado_product_id = odoo_api.env['product.product'].search([('name', '=', papel_cortado_name)])
                if not papel_cortado_product_id:
                    _logger.error(f"    ❌ Error: No se encontró el producto de papel cortado '{papel_cortado_name}' en Odoo.")
                    continue
                
                hojas_necesarias = math.ceil(bw_pages / pages_per_sheet)
                interior_components = [{'product_id': papel_cortado_product_id[0], 'quantity': hojas_necesarias}]

                interior_operations = [
                    {'name': 'Imprimir Interior', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_8310'], 'bmg_op_key': 'IMPRIMIR_INTERIOR_BYN'},
                    {'name': 'Guillotinar Interior', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['GUILLOTINA'], 'bmg_op_key': 'GUILLOTINAR_INTERIOR'},
                ]
                crear_ldm(odoo_api, interior_final_product_id, interior_components, interior_operations, trabajo)

            elif es_solo_color:
                _logger.info("  - Preparando LdM para el INTERIOR (100% Color)...")
                color_interior_product_name = f"[INTERIOR] {trabajo['title']}"
                color_interior_default_code = f"COMP-INT-{trabajo['order_code']}-{trabajo['line_number']}"
                interior_final_product_id = crear_o_buscar_producto(odoo_api, color_interior_product_name, color_interior_default_code)

                papel_color_code_api = trabajo.get('color_paper_type')
                papel_color_nombre = mapeos.MAPEO_NOMBRES_PAPEL.get(papel_color_code_api, "")
                if not papel_color_nombre:
                    _logger.error(f"    ❌ Error: No se encontró mapeo para el papel Color '{papel_color_code_api}'.")
                    continue

                grammage_match = re.search(r'(\d+)', papel_color_nombre)
                if not grammage_match:
                    _logger.error(f"    ❌ Error: No se pudo extraer el gramaje de '{papel_color_nombre}'")
                    continue
                grammage = grammage_match.group(1)
                nombre_base_papel_color = papel_color_nombre.replace(grammage, '').strip()
                
                try:
                    ancho, alto = papel_folder.split('x')
                    dimensiones_formateadas = f"{float(ancho):.1f}x{float(alto):.1f}"
                except ValueError:
                    dimensiones_formateadas = papel_folder

                papel_cortado_color_name = f"Papel {nombre_base_papel_color} {grammage}gr {dimensiones_formateadas}cm"
                papel_cortado_color_product_id = odoo_api.env['product.product'].search([('name', '=', papel_cortado_color_name)])
                if not papel_cortado_color_product_id:
                    _logger.error(f"    ❌ Error: No se encontró el producto de papel cortado '{papel_cortado_color_name}' en Odoo.")
                    continue
                    
                hojas_color_necesarias = math.ceil(color_pages / pages_per_sheet)
                color_components = [{'product_id': papel_cortado_color_product_id[0], 'quantity': hojas_color_necesarias}]
                
                color_operations = [{'name': 'Imprimir Interior Color', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_7200'], 'bmg_op_key': 'IMPRIMIR_INTERIOR_COLOR'}]
                crear_ldm(odoo_api, interior_final_product_id, color_components, color_operations, trabajo)

            elif es_mixto:
                _logger.info("  - Preparando LdM para el componente INTERIOR A COLOR (Mixto)...")
                papel_color_code_api = trabajo.get('color_paper_type')
                papel_color_nombre = mapeos.MAPEO_NOMBRES_PAPEL.get(papel_color_code_api, "")
                if not papel_color_nombre:
                    _logger.error(f"    ❌ Error: No se encontró mapeo para el papel Color '{papel_color_code_api}'.")
                    continue

                color_interior_component_name = f"[COMP-INT-COLOR] {trabajo['title']}"
                color_interior_component_default_code = f"SUBCOMP-INT-C-{trabajo['order_code']}-{trabajo['line_number']}"
                color_interior_component_id = crear_o_buscar_producto(odoo_api, color_interior_component_name, color_interior_component_default_code)

                grammage_match = re.search(r'(\d+)', papel_color_nombre)
                if not grammage_match:
                    _logger.error(f"    ❌ Error: No se pudo extraer el gramaje de '{papel_color_nombre}'")
                    continue
                grammage = grammage_match.group(1)
                nombre_base_papel_color = papel_color_nombre.replace(grammage, '').strip()
                
                try:
                    ancho, alto = papel_folder.split('x')
                    dimensiones_formateadas = f"{float(ancho):.1f}x{float(alto):.1f}"
                except ValueError:
                    dimensiones_formateadas = papel_folder

                papel_cortado_color_name = f"Papel {nombre_base_papel_color} {grammage}gr {dimensiones_formateadas}cm"
                papel_cortado_color_product_id = odoo_api.env['product.product'].search([('name', '=', papel_cortado_color_name)])
                if not papel_cortado_color_product_id:
                    _logger.error(f"    ❌ Error: No se encontró el producto de papel cortado '{papel_cortado_color_name}' en Odoo.")
                    continue
                
                hojas_color_necesarias = math.ceil(color_pages / pages_per_sheet)
                color_components = [{'product_id': papel_cortado_color_product_id[0], 'quantity': hojas_color_necesarias}]
                color_operations = [{'name': 'Imprimir Interior Color', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_7200'], 'bmg_op_key': 'IMPRIMIR_INTERIOR_COLOR'}]
                crear_ldm(odoo_api, color_interior_component_id, color_components, color_operations, trabajo)

                _logger.info("  - Preparando LdM para el INTERIOR (Mixto, compaginado)...")
                interior_product_name = f"[INTERIOR] {trabajo['title']}"
                interior_default_code = f"COMP-INT-{trabajo['order_code']}-{trabajo['line_number']}"
                interior_final_product_id = crear_o_buscar_producto(odoo_api, interior_product_name, interior_default_code)

                papel_byn_code_api = trabajo.get('bw_paper_type')
                papel_byn_nombre = mapeos.MAPEO_NOMBRES_PAPEL.get(papel_byn_code_api, "")
                if not papel_byn_nombre:
                    _logger.error(f"    ❌ Error: No se encontró mapeo para el papel ByN '{papel_byn_code_api}'.")
                    continue

                grammage_match = re.search(r'(\d+)', papel_byn_nombre)
                if not grammage_match:
                    _logger.error(f"    ❌ Error: No se pudo extraer el gramaje de '{papel_byn_nombre}'")
                    continue
                grammage = grammage_match.group(1)
                nombre_base_papel_byn = papel_byn_nombre.replace(grammage, '').strip()
                
                try:
                    ancho, alto = papel_folder.split('x')
                    dimensiones_formateadas = f"{float(ancho):.1f}x{float(alto):.1f}"
                except ValueError:
                    dimensiones_formateadas = papel_folder

                papel_cortado_byn_name = f"Papel {nombre_base_papel_byn} {grammage}gr {dimensiones_formateadas}cm"
                papel_cortado_byn_product_id = odoo_api.env['product.product'].search([('name', '=', papel_cortado_byn_name)])
                if not papel_cortado_byn_product_id:
                    _logger.error(f"    ❌ Error: No se encontró el producto de papel cortado '{papel_cortado_byn_name}' en Odoo.")
                    continue
                
                hojas_byn_necesarias = math.ceil(bw_pages / pages_per_sheet)
                
                # El interior final se compone del papel ByN y del sub-producto de color
                final_interior_components = [
                    {'product_id': papel_cortado_byn_product_id[0], 'quantity': hojas_byn_necesarias},
                    {'product_id': color_interior_component_id, 'quantity': 1}
                ]

                final_interior_operations = [
                    {'name': 'Imprimir Interior', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['IMPRESORA_8310'], 'bmg_op_key': 'IMPRIMIR_INTERIOR_BYN'},
                    {'name': 'Guillotinar Interior', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['GUILLOTINA'], 'bmg_op_key': 'GUILLOTINAR_INTERIOR'},
                ]
                crear_ldm(odoo_api, interior_final_product_id, final_interior_components, final_interior_operations, trabajo)
            
            else:
                _logger.error(f"    ❌ Error: No se pudo determinar el tipo de interior para el trabajo {order_code}-{line_number} (Páginas ByN: {bw_pages}, Páginas Color: {color_pages}).")
                continue

            _logger.info("  - Preparando LdM para el LIBRO FINAL...")
            final_components = [
                {'product_id': tapa_product_id, 'quantity': 1},
                {'product_id': interior_final_product_id, 'quantity': 1},
            ]
            final_operations = [
                {'name': 'Juntar Tapas e Interior', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['MESA_MULTITAREA'], 'bmg_op_key': 'JUNTAR_TAPAS_INTERIOR'},
                {'name': 'Encuadernar', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['ENCUADERNADORA_HORIZON'], 'bmg_op_key': 'ENCUADERNAR'},
                {'name': 'Guillotinado Final', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['GUILLOTINA'], 'bmg_op_key': 'GUILLOTINADO_FINAL'},
                {'name': 'Empacar', 'workcenter_ext_id': mapeos.MAPEO_CENTROS_TRABAJO['EMPAQUETADORA'], 'bmg_op_key': 'EMPACAR'},
            ]
            crear_ldm(odoo_api, libro_product_id, final_components, final_operations, trabajo)

            _logger.info("  - Creando Orden de Fabricación principal...")

            bom_id_para_usar = None
            bom_ids = odoo_api.env['mrp.bom'].search([('product_id', '=', libro_product_id)], limit=1)
            if bom_ids:
                bom_id_para_usar = bom_ids[0]
            
            if not bom_id_para_usar:
                product_info = odoo_api.env['product.product'].browse(libro_product_id)
                bom_ids = odoo_api.env['mrp.bom'].search([
                    ('product_tmpl_id', '=', product_info.product_tmpl_id.id),
                    ('product_id', '=', False)
                ], limit=1)
                if bom_ids:
                    bom_id_para_usar = bom_ids[0]

            if not bom_id_para_usar:
                _logger.error(f"    ❌ Error CRÍTICO: No se pudo encontrar la LdM para la variante {libro_product_id} después de haberla creado/actualizado.")
                continue
            
            _logger.info(f"    -> Usando LdM específica ID: {bom_id_para_usar} para la OF.")

            sale_order = so_model.browse(trabajo['odoo_sale_order_id'])
            procurement_group_id = None
            if sale_order.procurement_group_id:
                procurement_group_id = sale_order.procurement_group_id.id
                _logger.info(f"  -> Grupo de Abastecimiento encontrado en SO. ID: {procurement_group_id}")
            else:
                _logger.info("  -> ⚠️  Advertencia: No se encontró Grupo de Abastecimiento en el SO. Intentando buscar/crear...")
                existing_group_ids = procurement_group_model.search([('name', '=', sale_order.name)], limit=1)
                if existing_group_ids:
                    procurement_group_id = existing_group_ids[0]
                    sale_order.write({'procurement_group_id': procurement_group_id})
                    _logger.info(f"  -> ✅ Grupo de Abastecimiento existente encontrado y asignado con ID: {procurement_group_id}")
                else:
                    try:
                        new_group_id = procurement_group_model.create({'name': sale_order.name, 'sale_id': sale_order.id})
                        sale_order.write({'procurement_group_id': new_group_id})
                        procurement_group_id = new_group_id
                        _logger.info(f"  -> ✅ Grupo de Abastecimiento nuevo creado y asignado con ID: {procurement_group_id}")
                    except Exception as e:
                        _logger.error(f"  -> ❌ Error al crear Grupo de Abastecimiento: {e}")
                        raise
            
            of_vals = {
                'product_id': libro_product_id,
                'product_qty': trabajo.get('quantity_requested', 1),
                'bom_id': bom_id_para_usar,
                'origin': sale_order.name,
                'procurement_group_id': procurement_group_id,
                mapeos.ODOO_MRP_PRODUCTION_BMG_ORDER_LINE_FIELD: trabajo.get('line_number'),
            }
            new_of_id = mrp_production_model.create(of_vals)
            _logger.info(f"    -> OF Principal {new_of_id} creada en borrador.")

            # Asignar un nombre descriptivo pero único usando la secuencia original de Odoo
            of_record = mrp_production_model.browse(new_of_id)
            if of_record.name:
                desc_name = f"{of_record.name} - {trabajo.get('order_code')}-{trabajo.get('line_number')} {trabajo.get('title')} (SO: {sale_order.name})"
                of_record.write({'name': desc_name[:255]})

            _logger.info("  - Confirmando OF principal y su descendencia (hijas, nietas, etc.)...")
            
            try:
                of_record.action_confirm()
                _logger.info(f"    -> OF Principal {new_of_id} confirmada.")
            except Exception as e:
                _logger.error(f"    ❌ Error al confirmar la OF principal {new_of_id}: {e}")
                raise

            nombre_origen_so = sale_order.name
            if not nombre_origen_so:
                _logger.warning("    -> ⚠️ No se puede iniciar la búsqueda de descendencia, el SO no tiene nombre.")
            else:
                import time
                time.sleep(3) 

                origenes_a_buscar = {nombre_origen_so}
                ofs_procesadas = {new_of_id}

                while True:
                    _logger.info(f"  - Buscando OFs en borrador con orígenes: {list(origenes_a_buscar)}")
                    
                    ofs_encontradas_ids = mrp_production_model.search([
                        ('origin', 'in', list(origenes_a_buscar)),
                        ('state', '=', 'draft'),
                        ('id', 'not in', list(ofs_procesadas))
                    ])

                    if not ofs_encontradas_ids:
                        _logger.info("    -> ✅ No se encontraron nuevas OFs descendientes en borrador. Proceso finalizado.")
                        break 

                    _logger.info(f"    -> Se encontraron {len(ofs_encontradas_ids)} nuevas OFs descendientes. Procesando...")
                    for of_id in ofs_encontradas_ids:
                        try:
                            of_hija_record = mrp_production_model.browse(of_id)
                            
                            write_vals = {
                                mapeos.ODOO_MRP_PRODUCTION_BMG_ORDER_LINE_FIELD: trabajo.get('line_number')
                            }
                            
                            nuevo_nombre = ""
                            product_name = of_hija_record.product_id.name or ""
                            book_title = trabajo.get('title', '')

                            if product_name.startswith('[TAPA]'):
                                nuevo_nombre = f"{trabajo.get('order_code')}-{trabajo.get('line_number')} tapa de {book_title} (SO: {sale_order.name})"
                            elif product_name.startswith('[INTERIOR]'):
                                nuevo_nombre = f"{trabajo.get('order_code')}-{trabajo.get('line_number')} interior de {book_title} (SO: {sale_order.name})"
                            
                            if nuevo_nombre and of_hija_record.name:
                                write_vals['name'] = f"{of_hija_record.name} - {nuevo_nombre}"[:255]

                            _logger.info(f"      -> Asignando datos (Line Number, Nombre) a OF hija {of_id}...")
                            of_hija_record.write(write_vals) # Update name and custom line field on mrp.production

                            _logger.info(f"      -> Confirmando OF {of_id} ({of_hija_record.product_id.name})...")
                            of_hija_record.action_confirm()
                            
                            if of_hija_record.name:
                                _logger.info(f"        -> Añadiendo nuevo origen a la búsqueda: '{of_hija_record.name}'")
                                origenes_a_buscar.add(of_hija_record.name)
                            
                            ofs_procesadas.add(of_id)
                            time.sleep(0.5) 

                        except Exception as e_desc:
                            _logger.error(f"      ❌ Error al confirmar OF {of_id}: {e_desc}")
                            ofs_procesadas.add(of_id)
            
            _logger.info(f"    ✅ ¡Proceso de fabricación para OF {new_of_id} y su descendencia iniciado!")

            conn_update = db_conn.conectar_db()
            cursor_update = conn_update.cursor()
            cursor_update.execute(
                f"UPDATE trabajos SET odoo_mrp_order_id = ?, estado_fabricacion = '{mapeos.LOCAL_DB_STATUS_OF_CREADA}' WHERE order_code = ? AND line_number = ?",
                (new_of_id, order_code, line_number)
            )
            conn_update.commit()
            conn_update.close()
            _logger.info(f"  -> 💾 Base de datos local actualizada con el ID de la OF.")

        except Exception as e:
            _logger.error(f"  -> ❌❌ ERROR DETALLADO en Script 05: {e} ❌❌")
            mensaje_error = f"Ocurrió un error fatal no controlado al procesar la OF para el pedido {order_code}-{line_number}.\n\nError:\n{str(e)}"
            asunto = f"Error INESPERADO en Script 05 para pedido {order_code}-{line_number}"
            enviar_email(asunto, mensaje_error)
            try:
                so_record = odoo_api.env['sale.order'].browse(trabajo['odoo_sale_order_id'])
                so_record.message_post(body=mensaje_error, message_type='comment', subtype_xmlid='mail.mt_note')
            except Exception as chat_e:
                _logger.error(f"  -> ❌ Error al publicar en Chatter para SO ID {trabajo['odoo_sale_order_id']}: {chat_e}")


    _logger.info(f"\n--- Proceso de Script 5 finalizado. --- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")

if __name__ == "__main__":
    run()