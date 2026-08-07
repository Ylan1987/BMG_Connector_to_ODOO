# -*- coding: utf-8 -*-
"""
Script 3: Creador de Oportunidades y Pedidos de Venta en Odoo.

- Lee la DB local en busca de pedidos que necesiten ser sincronizados.
- Guarda el ID del cliente principal en la DB local.
- Crea la Oportunidad en Odoo y actualiza la DB local con su ID.
- Crea el Pedido de Venta en Odoo.
- Guarda el ID del Pedido de Venta y de cada una de sus líneas en la DB local.
- Notifica por email los errores críticos que impiden la sincronización.
"""

import json
from datetime import datetime
import unicodedata

# Importar módulos comunes de la V2.0
from common import mapeos, db_conn, odoo_conn, bmg_estados_mapeo, meli_api
from common.notificador import enviar_email
import logging

_logger = logging.getLogger(__name__)

# --- FUNCIONES AUXILIARES ---

def limpiar_id(id_original, prefijo):
    if not id_original: return ''
    id_sin_prefijo = id_original[len(prefijo):] if id_original.startswith(prefijo) else id_original
    return id_sin_prefijo.lstrip('0')

def safe_float_conversion(value, default_value=0.0):
    if value is None: return default_value
    if isinstance(value, (int, float)): return float(value)
    if isinstance(value, str):
        try: return float(value.replace(',', ''))
        except ValueError: return default_value
    return default_value

def normalize_text(text):
    if not text: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()

def _actualizar_variant_id_db(order_code, line_number, variant_id):
    conn = db_conn.conectar_db();
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE trabajos SET odoo_product_variant_id = ? WHERE order_code = ? AND line_number = ?", (variant_id, order_code, line_number))
        conn.commit()
    finally:
        conn.close()

def _actualizar_descripcion_db(order_code, line_number, descripcion):
    conn = db_conn.conectar_db();
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE trabajos SET descripcion_detalle_libro = ? WHERE order_code = ? AND line_number = ?", (descripcion, order_code, line_number))
        conn.commit()
    finally:
        conn.close()

# --- LÓGICA PRINCIPAL DE ODOO ---

def buscar_cliente_existente(odoo_api, trabajo):
    partner_model = odoo_api.env['res.partner']
    order_type = trabajo.get('order_type', '')
    publisher_facility = trabajo.get('publisher_facility', '').upper()
    es_edist_uno_a_uno = order_type == mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1

    if not es_edist_uno_a_uno and publisher_facility != mapeos.BMG_PUBLISHER_FACILITY_LAD:
        partner_ids = partner_model.search([('name', '=', mapeos.ODOO_PARTNER_BIBLIOMANAGER)])
        if partner_ids:
            print(f"  -> Pedido Internacional POD. Cliente asignado a Bibliomanager ID: {partner_ids[0]}")
            return partner_ids[0]
        else:
            print(f"  -> ❌ Error Crítico: No se encontró el cliente '{mapeos.ODOO_PARTNER_BIBLIOMANAGER}' en Odoo."); return None

    if mapeos.BMG_ORDER_TYPE_EDIST_GENERIC in order_type:
        channel_id_limpio = limpiar_id(str(trabajo.get('channel', '')).strip(), '')
        if not channel_id_limpio: 
            print(f"  -> ❌ Error: Pedido {mapeos.BMG_ORDER_TYPE_EDIST_GENERIC} sin Channel ID."); return None
        partner_ids = partner_model.search([('x_channel_id', '=', channel_id_limpio)])
        if partner_ids: return partner_ids[0]
        else: 
            print(f"  -> ❌ Error Crítico: Cliente con Channel ID '{channel_id_limpio}' (Librero) NO EXISTE en Odoo."); return None
    else:
        publisher_id_limpio = limpiar_id(str(trabajo.get('publisher_id', '')).strip(), mapeos.BMG_PUBLISHER_ID_PREFIX)
        if not publisher_id_limpio: 
            print(f"  -> ❌ Error: Pedido {mapeos.BMG_ORDER_TYPE_POD} sin Publisher ID."); return None
        partner_ids = partner_model.search([('x_publisher_id', '=', publisher_id_limpio)])
        if partner_ids: return partner_ids[0]
        else: 
            print(f"  -> ❌ Error Crítico: Cliente con Publisher ID '{publisher_id_limpio}' (Editor) NO EXISTE en Odoo."); return None

def crear_oportunidad(odoo_api, trabajo, cliente_id):
    lead_model = odoo_api.env['crm.lead']
    order_code = trabajo.get('order_code')
    oportunidad_nombre = f"{mapeos.ODOO_OPPORTUNITY_NAME_PREFIX}{order_code}"
    lead_ids = lead_model.search([('name', '=', oportunidad_nombre), ('partner_id', '=', cliente_id)])
    if lead_ids: return lead_ids[0]
    lead_vals = {
        'name': oportunidad_nombre, 'partner_id': cliente_id, 'type': 'opportunity',
        'x_business_unit': trabajo.get('business_unit', ''), 'x_order_type': trabajo.get('order_type', '')
    }
    try:
        return lead_model.create(lead_vals)
    except Exception as e:
        print(f"  -> ❌ Error al crear la oportunidad en Odoo: {e}"); return None

def _get_or_create_attribute_value(odoo_api, template_id, attribute_name, value_name, create_if_not_found=False):
    cache_value_name = "__CUSTOM_PLACEHOLDER__" if create_if_not_found and attribute_name not in ['Encuadernado', 'Papel Libro ByN', 'Impresión de tapa', 'Laminado Tapa Libro', 'Papel Libro Color', 'Orientación', 'Sangrado', 'Tamaño Producción', 'Termosellado individual'] else value_name
    conn_cache = db_conn.conectar_db(); cursor_cache = conn_cache.cursor()
    cursor_cache.execute("SELECT odoo_id FROM odoo_cache WHERE odoo_url = ? AND attribute_name = ? AND value_name = ?", (mapeos.ODOO_URL, attribute_name, cache_value_name))
    cached_result = cursor_cache.fetchone(); conn_cache.close()
    if cached_result: return cached_result['odoo_id']

    print(f"   [API] Buscando Atributo: '{attribute_name}' con Valor: '{value_name}'")
    attr_line_model = odoo_api.env['product.template.attribute.line']; value_model = odoo_api.env['product.attribute.value']; ptav_model = odoo_api.env['product.template.attribute.value']
    attr_line_ids = attr_line_model.search([('product_tmpl_id', '=', template_id), ('attribute_id.name', '=', attribute_name)])
    if not attr_line_ids: return None
    attribute_line = attr_line_model.browse(attr_line_ids[0]); correct_attribute_id = attribute_line.attribute_id.id; final_ptav_id = None

    if create_if_not_found:
        custom_value_ids = value_model.search([('attribute_id', '=', correct_attribute_id), ('is_custom', '=', True)])
        if custom_value_ids:
            ptav_ids = ptav_model.search([('product_tmpl_id', '=', template_id), ('product_attribute_value_id', '=', custom_value_ids[0])])
            if ptav_ids: final_ptav_id = ptav_ids[0]
            else:
                try: final_ptav_id = ptav_model.create({'product_tmpl_id': template_id, 'attribute_line_id': attribute_line.id, 'product_attribute_value_id': custom_value_ids[0]})
                except: pass
    else:
        raw_value_ids = value_model.search([('attribute_id', '=', correct_attribute_id), ('name', '=', value_name)])
        raw_value_id = raw_value_ids[0] if raw_value_ids else None
        if raw_value_id:
            ptav_ids = ptav_model.search([('product_tmpl_id', '=', template_id), ('product_attribute_value_id', '=', raw_value_id)])
            if ptav_ids: final_ptav_id = ptav_ids[0]
    
    if final_ptav_id:
        conn_cache_write = db_conn.conectar_db(); cursor_cache_write = conn_cache_write.cursor()
        try: cursor_cache_write.execute("INSERT OR IGNORE INTO odoo_cache (odoo_url, attribute_name, value_name, odoo_id) VALUES (?, ?, ?, ?)", (mapeos.ODOO_URL, attribute_name, cache_value_name, final_ptav_id)); conn_cache_write.commit()
        finally: conn_cache_write.close()
    return final_ptav_id

def _determinar_tamano_produccion(width, height):
    sizes = {mapeos.ODOO_PRODUCT_SIZE_10_5X17: (100, 165), mapeos.ODOO_PRODUCT_SIZE_15_5X22_5: (156, 221), mapeos.ODOO_PRODUCT_SIZE_17X24: (171, 241)}
    for name, (prod_w, prod_h) in sizes.items():
        if (width <= prod_w and height <= prod_h) or (width <= prod_h and height <= prod_w): return name
    return mapeos.ODOO_PRODUCT_SIZE_22X30

def _crear_lineas_envio(odoo_api, trabajo_cabecera, shipping_product_id, moneda_code_pedido, cliente_id, shipping_product_name, meli_data=None, analytic_accounts=None):
    lineas_envio = []
    descuento_general_envio = False; descuento_biblioteca_carrier = False
    try:
        partner_fields = ['property_delivery_carrier_id']
        partner_data = odoo_api.env['res.partner'].search_read([('id', '=', cliente_id)], partner_fields)
        if partner_data and partner_data[0].get('property_delivery_carrier_id'):
            carrier_info = partner_data[0]['property_delivery_carrier_id']
            carrier_name = carrier_info[1] if isinstance(carrier_info, (list, tuple)) else ""
            if carrier_name == mapeos.ODOO_CARRIER_ENVIO_SIN_COSTO: descuento_general_envio = True
            elif carrier_name == mapeos.ODOO_CARRIER_ENVIO_BIBLIOTECA_SIN_COSTO: descuento_biblioteca_carrier = True
    except: pass

    datos_envio = json.loads(trabajo_cabecera.get('datos_envio_json', '[]'))
    if not datos_envio: return lineas_envio
        
    tax_model = odoo_api.env['account.tax']; es_envio_nacional = shipping_product_name == mapeos.ODOO_SHIPPING_PRODUCT_NACIONAL
    tax_ids_envio_std = tax_model.search([('name', '=', mapeos.ODOO_TAX_VENTAS_IVA_22 if es_envio_nacional else mapeos.ODOO_TAX_VENTAS_EXENTOS_IVA), ('type_tax_use', '=', mapeos.ODOO_TAX_TYPE_SALE)])
    tax_ids_envio_gratis = tax_model.search([('name', '=', mapeos.ODOO_TAX_ENTREGA_GRATUITA), ('type_tax_use', '=', mapeos.ODOO_TAX_TYPE_SALE)])

    for idx, envio in enumerate(datos_envio, 1):
        costo_envio_bruto = safe_float_conversion(envio.get('Costo_Envio')) 
        if meli_data and meli_data.get('shipping_cost') is not None:
            _logger.info(f"    -> [ML] Ajustando costo de envío: {meli_data['shipping_cost']} (BMG era: {costo_envio_bruto})")
            costo_envio_bruto = meli_data['shipping_cost']

        moneda_envio = envio.get('ShippingCurrency', mapeos.CURRENCY_UYU).upper()
        exchange_rate = safe_float_conversion(trabajo_cabecera.get('unit_currency_exchange'), default_value=1.0)
        costo_envio_final = costo_envio_bruto / exchange_rate if moneda_envio not in [mapeos.CURRENCY_USD, mapeos.CURRENCY_UYU] and exchange_rate > 0 else costo_envio_bruto
        if es_envio_nacional: costo_envio_final = costo_envio_final / (1 + mapeos.ODOO_TAX_VENTAS_IVA_22_RATE / 100)

        aplicar_descuento_linea = False
        if es_envio_nacional:
            if descuento_general_envio: aplicar_descuento_linea = True
            elif descuento_biblioteca_carrier:
                total_copies = sum(int(t.get('Copies', 0)) for t in envio.get('Titulos', []))
                texto_destino = normalize_text(f"{envio.get('Destino', '')} {envio.get('Direccion', '')}")
                if total_copies == 4 and (('biblioteca' in texto_destino and 'nacional' in texto_destino) or ('deposito' in texto_destino and 'legal' in texto_destino)):
                    aplicar_descuento_linea = True

        titulos_enviar_str = ""; total_peso_envio = 0
        if envio.get('Titulos'):
            titulos_enviar_str = "\n#### Títulos a enviar:\n"
            for t in envio['Titulos']:
                weight = safe_float_conversion(t.get('TotalWeight')); total_peso_envio += weight
                titulos_enviar_str += f"{t.get('Copies', 0)}x {t.get('Title', 'N/A')} (Peso est: {weight}g)\n"

        descripcion_envio = f"Datos de envío {idx}\nTipo de envío: {envio.get('Tipo_Envio', 'N/A')}\nOperador: {envio.get('Operador', 'N/A')}\nEmpresa: {envio.get('Empresa', 'N/A')}\nDestino: {envio.get('Destino', 'N/A')} - {envio.get('Ciudad', 'N/A')}\nDirección: {envio.get('Direccion', 'N/A')} {envio.get('ZIPCode', '')}\nContacto: {envio.get('Contacto', 'N/A')}\nTeléfono: {envio.get('Telefono', 'N/A')}\nPeso Total: {total_peso_envio}g\n{titulos_enviar_str}"

        es_entrega_gratuita = (costo_envio_final == 0) or aplicar_descuento_linea
        if costo_envio_final >= 0:
            linea_envio_vals = {'product_id': shipping_product_id, 'product_uom_qty': 1, 'price_unit': costo_envio_final, 'name': descripcion_envio.strip()}
            if es_entrega_gratuita:
                if aplicar_descuento_linea: linea_envio_vals['discount'] = 100.0
                linea_envio_vals['tax_id'] = [(6, 0, tax_ids_envio_gratis)] if tax_ids_envio_gratis else [(6, 0, tax_ids_envio_std)]
            elif tax_ids_envio_std: linea_envio_vals['tax_id'] = [(6, 0, tax_ids_envio_std)]
            
            if analytic_accounts:
                account_id = analytic_accounts.get('PRODUCCION_TERCERIZADA')
                if account_id:
                    linea_envio_vals['analytic_distribution'] = {str(account_id): 100}
                    print(f"    -> [DEBUG_ANALYTIC] Asignando Cuenta 'Produccion Tercerizada' (ID: {account_id}) a línea de envío.")
                else:
                    print(f"    -> [DEBUG_ANALYTIC] ⚠️ No se encontró ID para 'Produccion Tercerizada' en líneas de envío.")
            else:
                print(f"    -> [DEBUG_ANALYTIC] ⚠️ analytic_accounts está vacío o es None en líneas de envío.")
            
            lineas_envio.append((0, 0, linea_envio_vals))
    return lineas_envio

def gestionar_contacto_mercadolibros(odoo_api, trabajo):
    partner_model = odoo_api.env['res.partner']; datos_envio = json.loads(trabajo.get('datos_envio_json', '[]'))
    if not datos_envio: return None, None
    envio = datos_envio[0]; contact_name = envio.get('Contacto', '').strip(); direccion = envio.get('Direccion', '').strip().lower(); ciudad = envio.get('Ciudad', '').strip()
    nombre_final = contact_name.split('-')[1].strip() if 'mercadolibros -' in contact_name.lower() else contact_name
    if not nombre_final: return None, None

    # Intentamos buscar el contacto primero para NO duplicar (Buscamos sueltos)
    existing_partner_ids = partner_model.search([
        ('name', '=', nombre_final),
        ('type', '=', 'delivery')
    ], limit=1)

    if existing_partner_ids:
        print(f"    - 👤 Contacto existente encontrado para factura/envío: {nombre_final} (ID: {existing_partner_ids[0]})")
        return existing_partner_ids[0], existing_partner_ids[0]

    parent_contact_ids = partner_model.search([('x_channel_id', '=', mapeos.MERCADOLIBROS_CHANNEL_ID)])
    if not parent_contact_ids: return None, None
    parent_contact = partner_model.browse(parent_contact_ids[0]); parent_country_id = parent_contact.country_id.id
    if not parent_country_id: return None, None
    
    # Buscar el brand_id de MercadoLibros
    brand_id = None
    try:
        brand_ids = odoo_api.env['res.company.brand'].search([('name', 'ilike', 'MercadoLibros')], limit=1)
        brand_id = brand_ids[0] if brand_ids else None
    except: pass

    try: 
        print(f"    - 🆕 Creando nuevo contacto SUELTO para factura/envío: {nombre_final}")
        partner_vals = {'name': nombre_final, 'country_id': parent_country_id, 'type': 'delivery'}
        if brand_id: partner_vals['brand_id'] = brand_id
        id_facturacion = partner_model.create(partner_vals)
    except Exception as e: print(f"  -> ❌ Error: {e}"); return None, None
    id_envio = id_facturacion
    empresa = envio.get('Empresa', '').strip().lower()
    es_retira_en_lad = (
        'retira en lad' in normalize_text(direccion)
        or 'retira en lad' in normalize_text(empresa)
        or 'convencion 1319' in normalize_text(direccion)
    )
    if es_retira_en_lad:
        ids_lad = partner_model.search([('name', '=', mapeos.ODOO_PARTNER_RETIRA_IMPrenta)])
        if ids_lad: id_envio = ids_lad[0]
    elif mapeos.ODOO_SHIPPING_METHOD_MERCADOENVIOS.lower() in direccion: partner_model.write([id_facturacion], {'street': f"{mapeos.ODOO_SHIPPING_METHOD_MERCADOENVIOS}: {envio.get('Direccion', '')}", 'city': ciudad})
    else: partner_model.write([id_facturacion], {'street': envio.get('Direccion', ''), 'city': ciudad})
    return id_facturacion, id_envio

def crear_pedido_venta(odoo_api, trabajos, cliente_id, oportunidad_id, cliente_facturacion_id=None, cliente_envio_id=None, analytic_accounts=None):
    product_template_model = odoo_api.env['product.template']; product_model = odoo_api.env['product.product']; currency_model = odoo_api.env['res.currency']; so_model = odoo_api.env['sale.order']
    trabajo_cabecera = trabajos[0]; template_name = mapeos.PRODUCTO_PLANTILLA_LIBRO if trabajo_cabecera.get('printing_facility', '').upper() == mapeos.BMG_PUBLISHER_FACILITY_LAD else mapeos.PRODUCTO_PLANTILLA_LIBRO_FUERA_UY
    template_ids = product_template_model.search([('name', '=', template_name)])
    if not template_ids: return None
    template_id = template_ids[0]; template_record = product_template_model.browse(template_id)
    income_account_id = template_record.property_account_income_id.id
    if not income_account_id: return None

    shipping_product_name = mapeos.ODOO_SHIPPING_PRODUCT_NACIONAL if trabajo_cabecera.get('printing_facility', '').upper() == mapeos.BMG_PUBLISHER_FACILITY_LAD else mapeos.ODOO_SHIPPING_PRODUCT_EXTERIOR
    shipping_product_ids = product_model.search([('name', '=', shipping_product_name)], limit=1)
    if not shipping_product_ids: return None
    shipping_product_id = shipping_product_ids[0]; lineas_de_pedido = []; moneda_id = None

    # 1. Obtener detalles de MercadoLibre si la sincro está activa y el cliente es MercadoLibros
    meli_data = None; meli_no_encontrado = False; meli_order_id_detectado = None
    if mapeos.ML_SINCRO_ACTIVADA:
        # Buscamos el ID del cliente MercadoLibros solo si la flag está encendida
        ml_partner_ids = odoo_api.env['res.partner'].search([('x_channel_id', '=', mapeos.MERCADOLIBROS_CHANNEL_ID)], limit=1)
        if ml_partner_ids and cliente_id == ml_partner_ids[0]:
            datos_envio_list = json.loads(trabajo_cabecera.get('datos_envio_json', '[]'))
            if datos_envio_list:
                envio_data = datos_envio_list[0]; empresa_raw = envio_data.get('Empresa', '')
                if 'MELI-' in empresa_raw.upper():
                    meli_order_id_detectado = empresa_raw.upper().replace('MELI-', '').strip()
                    # ESTA ES LA ÚNICA LLAMADA A MELI: Trae precios y envío de una vez
                    meli_data = meli_api.obtener_detalle_orden_ml(meli_order_id_detectado)
                    if not meli_data:
                        meli_no_encontrado = True
                    else:
                        # Guardar el estado en la DB local para que el script 04 no tenga que re-consultar
                        try:
                            m_status = meli_data.get('raw_data', {}).get('status')
                            if m_status:
                                conn_m = db_conn.conectar_db(); cursor_m = conn_m.cursor()
                                cursor_m.execute("UPDATE trabajos SET meli_status = ? WHERE order_code = ?", (m_status, trabajo_cabecera['order_code']))
                                conn_m.commit(); conn_m.close()
                        except Exception as e_db: print(f"  -> ⚠️ Error guardando meli_status: {e_db}")

    for trabajo in trabajos:
        print(f"  -> 🛒 Procesando línea #{trabajo.get('line_number')} para crear variante...")
        width = safe_float_conversion(trabajo.get('width')); height = safe_float_conversion(trabajo.get('height')); orientacion_borde = "en Borde Largo" if height >= width else "en Borde Corto"
        binding_code = trabajo.get('binding'); base_encuadernado = mapeos.MAPEO_ENCUADERNADO.get(binding_code); valor_encuadernado_final = base_encuadernado
        if base_encuadernado and base_encuadernado in ['Cosido con 2 grapas', 'Lomo cuadrado', 'Rulo metálico']: valor_encuadernado_final = f"{base_encuadernado} {orientacion_borde}"
        
        bw_paper_code = trabajo.get('bw_paper_type'); color_paper_code = trabajo.get('color_paper_type'); laminate_code = trabajo.get('laminate'); cover_printing_code = trabajo.get('cover_printing_type'); cover_paper_code = trabajo.get('cover_paper_type')
        papel_bw_nombre = mapeos.MAPEO_NOMBRES_PAPEL.get(bw_paper_code, bw_paper_code or 'N/A'); papel_color_nombre = mapeos.MAPEO_NOMBRES_PAPEL.get(color_paper_code, color_paper_code or 'N/A')
        impresion_tapa_nombre = mapeos.MAPEO_IMPRESION_TAPA.get(cover_printing_code, cover_printing_code or 'N/A'); laminado_nombre = mapeos.MAPEO_LAMINADO.get(laminate_code, laminate_code or 'N/A')
        
        variant_id = trabajo.get('odoo_product_variant_id'); custom_values_to_pass = []
        if not variant_id:
            atributos_de_variante = {
                'Encuadernado': valor_encuadernado_final, 'Papel Libro ByN': papel_bw_nombre, 'Impresión de tapa': impresion_tapa_nombre, 'Laminado Tapa Libro': laminado_nombre, 'Papel Libro Color': papel_color_nombre,
                'Orientación': mapeos.PRODUCT_ORIENTATION_VERTICAL if height >= width else mapeos.PRODUCT_ORIENTATION_LANDSCAPE,
                'Sangrado': mapeos.PRODUCT_BLEED_YES if safe_float_conversion(trabajo.get('bleed')) > 0 else mapeos.PRODUCT_BLEED_NO,
                'Tamaño Producción': _determinar_tamano_produccion(width, height),
                'Termosellado individual': mapeos.PRODUCT_SEALING_YES if trabajo.get('sealing') == 'YES' else mapeos.PRODUCT_SEALING_NO,
            }
            atributos_custom = {'Título': trabajo.get('title'), 'ISBN': trabajo.get('code'), 'PAP': limpiar_id(trabajo.get('title_id'), 'PAP'), 'Espesor de lomo (en mm)': str(trabajo.get('spine', '0')), 'Tamaño cerrado (cm)': f"{width/10}x{height/10}", 'Páginas ByN': str(trabajo.get('bw_pages', '0')), 'Páginas color': str(trabajo.get('color_pages', '0'))}
            flaps_width = safe_float_conversion(trabajo.get('flaps_width'))
            if flaps_width > 0: atributos_de_variante['Solapas'] = "Personalizado"; atributos_custom['Solapas'] = str(flaps_width)
            else: atributos_de_variante['Solapas'] = mapeos.PRODUCT_BLEED_NO
            
            ptav_ids = []
            for attr_name, attr_value in atributos_de_variante.items():
                if not attr_value or attr_value == "No especificado": continue
                ptav_id = _get_or_create_attribute_value(odoo_api, template_id, attr_name, attr_value)
                if ptav_id: ptav_ids.append(ptav_id)
            for attr_name, attr_value in atributos_custom.items():
                if not attr_value: continue
                ptav_id_placeholder = _get_or_create_attribute_value(odoo_api, template_id, attr_name, attr_value, True)
                if ptav_id_placeholder: ptav_ids.append(ptav_id_placeholder); custom_values_to_pass.append((ptav_id_placeholder, attr_value))

            domain = [('product_tmpl_id', '=', template_id)] + [('product_template_attribute_value_ids', '=', ptav_id) for ptav_id in ptav_ids]
            variant_ids = product_model.search(domain)
            if variant_ids: variant_id = variant_ids[0]
            else:
                try: variant_id = product_model.create({'product_tmpl_id': template_id, 'product_template_attribute_value_ids': [(6, 0, ptav_ids)], 'property_account_income_id': income_account_id})
                except Exception as e: print(f"-> ❌ Error creando variante: {e}"); return None
            _actualizar_variant_id_db(trabajo['order_code'], trabajo['line_number'], variant_id); trabajo['odoo_product_variant_id'] = variant_id

        tax_ids = odoo_api.env['account.tax'].search([('name', '=', mapeos.ODOO_TAX_VENTAS_EXENTOS_IVA), ('type_tax_use', '=', mapeos.ODOO_TAX_TYPE_SALE)])
        moneda_code_actual = trabajo.get('unit_currency', mapeos.CURRENCY_UYU).upper(); descuento_porcentaje = 0.0
        publisher_facility = trabajo.get('publisher_facility', '').strip()
        if not (trabajo.get('order_type') == mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1) and publisher_facility != mapeos.BMG_PUBLISHER_FACILITY_LAD:
            moneda_code_actual = mapeos.CURRENCY_USD; descuento_porcentaje = mapeos.DISCOUNT_INTERNATIONAL_POD
        elif mapeos.BMG_ORDER_TYPE_EDIST_GENERIC in trabajo.get('order_type', '') and trabajo.get('channel') != mapeos.MERCADOLIBROS_CHANNEL_ID:
            upc = safe_float_conversion(trabajo.get('unit_price_channel')); up = safe_float_conversion(trabajo.get('unit_price'))
            if up > 0 and upc > 0: descuento_porcentaje = round((1 - upc / up) * 100)

        precio_unitario_final = safe_float_conversion(trabajo.get('unit_price_invoice') if moneda_code_actual == mapeos.CURRENCY_USD else trabajo.get('unit_price')) + safe_float_conversion(trabajo.get('unit_price_adjustment'))
        
        # --- DESCUENTO USD 1.5 PARA EXTRANJEROS (BU: eDistribucion, TIPO != eDistribucion) ---
        is_foreign = (publisher_facility != mapeos.BMG_PUBLISHER_FACILITY_LAD)
        is_bu_edist = ('edistribucion' in trabajo.get('business_unit', '').lower().replace('ó', 'o'))
        is_type_edist = ('edistrib' in trabajo.get('order_type', '').lower().replace('ó', 'o'))
        
        if is_foreign and is_bu_edist and not is_type_edist:
            precio_unitario_final = max(0.0, precio_unitario_final - 1.5)
            print(f"    -> 📉 Aplicando descuento de USD 1.5 (Editor extranjero, BU eDistribucion, Tipo POD). Nuevo precio: {precio_unitario_final}")

        if meli_data:
            isbn_bmg = str(trabajo.get('code') or '')
            pap_id_bmg = limpiar_id(trabajo.get('title_id'), 'PAP')
            
            precio_ml = None
            order_items = meli_data.get('raw_data', {}).get('order_items', [])
            
            for item_line in order_items:
                if item_line.get('_matched'):
                    continue
                    
                item_info = item_line.get('item', {})
                sku = str(item_info.get('seller_custom_field') or item_info.get('id') or '')
                
                # Buscar un item cuyo seller_sku contenga el TitleID limpio (pap_id_bmg)
                if pap_id_bmg and pap_id_bmg in sku:
                    precio_ml = safe_float_conversion(item_line.get('unit_price', 0.0))
                    item_line['_matched'] = True
                    break
                # Fallback al ISBN
                elif isbn_bmg and isbn_bmg in sku:
                    precio_ml = safe_float_conversion(item_line.get('unit_price', 0.0))
                    item_line['_matched'] = True
                    break

            if precio_ml is not None:
                _logger.info(f"    -> [ML] Coincidencia encontrada. Ajustando precio del libro (Ref BMG: {pap_id_bmg}/{isbn_bmg}): {precio_ml} (BMG era: {precio_unitario_final})")
                print(f"    -> [ML] Coincidencia encontrada. Ajustando precio del libro (Ref BMG: {pap_id_bmg}/{isbn_bmg}): {precio_ml} (BMG era: {precio_unitario_final})")
                precio_unitario_final = precio_ml
            else:
                _logger.warning(f"    -> [ML] Advertencia: No se encontró coincidencia en ML para el libro (Ref BMG: {pap_id_bmg}/{isbn_bmg}). Se usará el precio original BMG: {precio_unitario_final}")
                print(f"    -> [ML] ⚠️ Advertencia: No se encontró coincidencia en ML para el libro (Ref BMG: {pap_id_bmg}/{isbn_bmg}). Se usará el precio original BMG: {precio_unitario_final}")

        currency_ids = currency_model.search([('name', '=', moneda_code_actual)], limit=1)
        if currency_ids: moneda_id = currency_ids[0]
        
        prefijo_titulo = f"{publisher_facility}\n" if publisher_facility != mapeos.BMG_PUBLISHER_FACILITY_LAD and trabajo.get('order_type') != mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1 else ""
        descripcion_libro = f"{prefijo_titulo}{trabajo.get('title')} ({limpiar_id(trabajo.get('order_code'), mapeos.BMG_ORDER_CODE_PREFIX)}-{trabajo.get('line_number')}) {trabajo.get('code', 'N/A')}\nCantidad: {trabajo.get('quantity_requested', 'N/A')}\nTamaño: {trabajo.get('width', 'N/A')} x {trabajo.get('height', 'N/A')} mm\nUnidad de negocio: {trabajo.get('business_unit', 'N/A')}\nTipo: {trabajo.get('order_type', 'N/A')}\n\nInterior ByN\nPáginas: {trabajo.get('bw_pages', 'N/A')}\nPapel: {papel_bw_nombre}\nTintas: {mapeos.PRODUCT_INK_BW}\nComentarios: {trabajo.get('publisher_observations', 'N/A')}\n"
        if safe_float_conversion(trabajo.get('color_pages')) > 0: descripcion_libro += f"\nInsertos color\nPáginas: {trabajo.get('color_pages')}\nPapel: {papel_color_nombre}\n"
        descripcion_libro += f"\nTapas\nLomo: {trabajo.get('spine', 'N/A')} mm\nTintas: {impresion_tapa_nombre}\nPapel: {mapeos.MAPEO_NOMBRES_PAPEL.get(cover_paper_code, cover_paper_code or 'N/A')}\nSolapas: {safe_float_conversion(trabajo.get('flaps_width')) if safe_float_conversion(trabajo.get('flaps_width')) > 0 else mapeos.PRODUCT_BLEED_NO}\n\nTerminaciones\nEncuadernado: {valor_encuadernado_final}\nLaminado: {laminado_nombre}\n"
        _actualizar_descripcion_db(trabajo['order_code'], trabajo['line_number'], descripcion_libro)

        linea_vals = {
            'product_id': variant_id, 
            'product_uom_qty': trabajo.get('quantity_requested', 0), 
            'price_unit': precio_unitario_final, 
            'discount': descuento_porcentaje, 
            'name': descripcion_libro, 
            'tax_id': [(6, 0, tax_ids)], 
            'x_bmg_order_line': trabajo.get('line_number'), 
            'product_custom_attribute_value_ids': [(0, 0, {'custom_product_template_attribute_value_id': p, 'custom_value': v}) for p, v in custom_values_to_pass],
            # --- NUEVOS CAMPOS FINANCIEROS (MATEMÁTICA PURA) ---
            'x_origen_pais': trabajo.get('x_origen_pais'),
            'x_precio_canal': safe_float_conversion(trabajo.get('x_precio_canal')),
            'x_costo_impresion_uy': safe_float_conversion(trabajo.get('x_costo_impresion_uy')),
            'x_comision_traer_libreria_uy': safe_float_conversion(trabajo.get('x_comision_traer_libreria_uy')),
            'x_comision_traer_editor_uy': safe_float_conversion(trabajo.get('x_comision_traer_editor_uy')),
            'x_comision_editor_uy': safe_float_conversion(trabajo.get('x_comision_editor_uy')),
            'x_comision_traer_editor_bmg': safe_float_conversion(trabajo.get('x_comision_traer_editor_bmg')),
            'x_comision_editor_bmg': safe_float_conversion(trabajo.get('x_comision_editor_bmg')),
            'x_comision_bmg_propia': safe_float_conversion(trabajo.get('x_comision_bmg_propia')),
            'x_total_bmg_terceros': safe_float_conversion(trabajo.get('x_total_bmg_terceros')),
            'x_total_bmg_propio': safe_float_conversion(trabajo.get('x_total_bmg_propio')),
            'x_total_lad_uy': safe_float_conversion(trabajo.get('x_total_lad_uy'))
        }
        
        if analytic_accounts:
            # Determinamos si es Produccion Propia o Reventa según la planta de producción (printing_facility)
            # Si se produce en Uruguay (LAD), es PRODUCCION_PROPIA.
            printing_facility = (trabajo.get('printing_facility') or "").strip().upper()
            if printing_facility == mapeos.BMG_PUBLISHER_FACILITY_LAD:
                account_id = analytic_accounts.get('PRODUCCION_PROPIA')
                tipo_cuenta = "Produccion Propia"
            else:
                account_id = analytic_accounts.get('MERCADERIA_REVENTA')
                tipo_cuenta = "Mercadería de Reventa (no se produce)"
            
            if account_id: 
                linea_vals['analytic_distribution'] = {str(account_id): 100}
                print(f"    -> [DEBUG_ANALYTIC] Asignando Cuenta '{tipo_cuenta}' (ID: {account_id}) a línea de libro. (Printing Facility: {printing_facility})")
            else:
                print(f"    -> [DEBUG_ANALYTIC] ⚠️ No se encontró ID para '{tipo_cuenta}'. (Printing Facility: {printing_facility})")
        else:
            print(f"    -> [DEBUG_ANALYTIC] ⚠️ analytic_accounts está vacío o es None.")
        
        lineas_de_pedido.append((0, 0, linea_vals))

    if mapeos.PRODUCCION_ACTIVADA and trabajo_cabecera.get('order_type') == '1ra. impr. std' and trabajo_cabecera.get('publisher_facility', '').upper() == mapeos.BMG_PUBLISHER_FACILITY_LAD:
        try:
            prod_val_ids = product_model.search([('name', '=', 'Validación de diseños del cliente')], limit=1)
            if prod_val_ids: lineas_de_pedido.append((0, 0, {'product_id': prod_val_ids[0], 'product_uom_qty': 1, 'price_unit': 0}))
        except: pass

    if shipping_product_id:
        lineas_envio = _crear_lineas_envio(odoo_api, trabajo_cabecera, shipping_product_id, trabajos[-1].get('unit_currency', 'UYU'), cliente_id, shipping_product_name, meli_data, analytic_accounts)
        lineas_de_pedido.extend(lineas_envio)

    if not lineas_de_pedido: return None
    pricelist_ids = odoo_api.env['product.pricelist'].search([('currency_id', '=', moneda_id)], limit=1)
    if not pricelist_ids: return None
    
    # Determinar Marca (MercadoLibros si el canal coincide, sino LAD)
    brand_name = "LAD"
    ml_partner_ids = odoo_api.env['res.partner'].search([('x_channel_id', '=', mapeos.MERCADOLIBROS_CHANNEL_ID)], limit=1)
    if ml_partner_ids and cliente_id == ml_partner_ids[0]:
        brand_name = "MercadoLibros"
    
    brand_id = None
    try:
        brand_ids = odoo_api.env['res.company.brand'].search([('name', 'ilike', brand_name)], limit=1)
        brand_id = brand_ids[0] if brand_ids else None
    except: pass

    # 0. Búsqueda de SEGURIDAD contra duplicados en Odoo
    order_code = trabajo_cabecera['order_code']
    existing_so_ids = so_model.search([('client_order_ref', '=', order_code), ('state', '!=', 'cancel')], limit=1)
    if existing_so_ids:
        print(f"    -> ℹ️ El pedido {order_code} ya existe en Odoo (ID: {existing_so_ids[0]}). Saltando creación.")
        return existing_so_ids[0]

    so_vals = {'partner_id': cliente_id, 'opportunity_id': oportunidad_id, 'pricelist_id': pricelist_ids[0], 'currency_id': moneda_id, 'order_line': lineas_de_pedido, 'client_order_ref': order_code}
    if brand_id: so_vals['brand_id'] = brand_id
    if cliente_facturacion_id: so_vals['partner_invoice_id'] = cliente_facturacion_id
    if cliente_envio_id: so_vals['partner_shipping_id'] = cliente_envio_id

    try:
        new_so_id = so_model.create(so_vals)
        msg = f"**Estados BMG al crear Pedido de Venta {trabajo_cabecera['order_code']}:**\n"
        for t in trabajos: msg += f"- Línea {t['line_number']} ({t['title']}): {t['line_status']}\n"
        if meli_no_encontrado:
            msg += f"\n⚠️ **ALERTA MERCADOLIBRE:** No se encontró la orden {meli_order_id_detectado} en MercadoLibre. Se usaron datos de BMG."
        try: odoo_api.env['sale.order'].browse(new_so_id).message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
        except: pass
        return new_so_id
    except Exception as e: print(f"  -> ❌ Error crear SO: {e}"); return None

def run():
    print(f"--- Iniciando Script 3 --- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    conn = db_conn.conectar_db();
    if not conn: return
    cursor = conn.cursor()
    if mapeos.TEST_ORDER_CODE:
        _logger.info(f"  -> MODO DE PRUEBA: Procesando únicamente el pedido {mapeos.TEST_ORDER_CODE}")
        cursor.execute("SELECT DISTINCT order_code FROM trabajos WHERE order_code = ? AND odoo_sale_order_id IS NULL", (mapeos.TEST_ORDER_CODE,))
    else:
        cursor.execute(f"SELECT DISTINCT order_code FROM trabajos WHERE odoo_sale_order_id IS NULL AND estado_odoo = '{mapeos.LOCAL_DB_STATUS_LISTO_PARA_SINCRONIZAR}'")
    pedidos = [row['order_code'] for row in cursor.fetchall()]; conn.close()
    if not pedidos: return
    odoo_api = odoo_conn.conectar_odoo();
    if not odoo_api: return

    analytic_accounts = {'PRODUCCION_PROPIA': None, 'MERCADERIA_REVENTA': None, 'PRODUCCION_TERCERIZADA': None}
    print(f"  [DEBUG_ANALYTIC] Conectado a DB: {mapeos.ODOO_DB}")
    try:
        # Buscamos todas las cuentas y mapeamos por prefijo o nombre
        todas_las_cuentas = odoo_api.env['account.analytic.account'].search_read([], ['id', 'name'])
        print(f"  [DEBUG_ANALYTIC] Se encontraron {len(todas_las_cuentas)} cuentas analíticas en total.")
        
        # 1. Búsqueda TEXTUAL EXACTA (Prioridad Producción)
        for acc in todas_las_cuentas:
            name = acc['name']
            if name == 'Produccion Propia':
                analytic_accounts['PRODUCCION_PROPIA'] = acc['id']
                print(f"  [DEBUG_ANALYTIC] Asignada 'PRODUCCION_PROPIA' -> {name} (ID: {acc['id']})")
            elif name == 'Mercadería de Reventa (no se produce)':
                analytic_accounts['MERCADERIA_REVENTA'] = acc['id']
                print(f"  [DEBUG_ANALYTIC] Asignada 'MERCADERIA_REVENTA' -> {name} (ID: {acc['id']})")
            elif name == 'Produccion Tercerizada':
                analytic_accounts['PRODUCCION_TERCERIZADA'] = acc['id']
                print(f"  [DEBUG_ANALYTIC] Asignada 'PRODUCCION_TERCERIZADA' -> {name} (ID: {acc['id']})")

        # 2. Respaldo para Staging (solo si no se encontraron las de arriba)
        if not analytic_accounts['PRODUCCION_PROPIA']:
            for acc in todas_las_cuentas:
                if acc['name'] == 'Producción ID': 
                    analytic_accounts['PRODUCCION_PROPIA'] = acc['id']
                    print(f"  [DEBUG_ANALYTIC] Respaldo Staging: 'PRODUCCION_PROPIA' -> {acc['name']} (ID: {acc['id']})")
                if acc['name'] == 'Interno': 
                    analytic_accounts['MERCADERIA_REVENTA'] = acc['id']
                    print(f"  [DEBUG_ANALYTIC] Respaldo Staging: 'MERCADERIA_REVENTA' -> {acc['name']} (ID: {acc['id']})")
                if acc['name'] == 'Atención al Cliente PA': 
                    analytic_accounts['PRODUCCION_TERCERIZADA'] = acc['id']
                    print(f"  [DEBUG_ANALYTIC] Respaldo Staging: 'PRODUCCION_TERCERIZADA' -> {acc['name']} (ID: {acc['id']})")
    except Exception as e: 
        print(f"  [DEBUG_ANALYTIC] Error buscando cuentas: {e}")

    for order_code in pedidos:
        print(f"\n--- Procesando Pedido: {order_code} ---")
        conn = db_conn.conectar_db(); cursor = conn.cursor(); cursor.execute("SELECT * FROM trabajos WHERE order_code = ?", (order_code,)); grupo = [dict(row) for row in cursor.fetchall()]; conn.close()
        if not grupo: continue
        
        if any(safe_float_conversion(t.get('line_status_id')) in bmg_estados_mapeo.LISTA_ESTADOS_FINALES_IDS for t in grupo):
            print(f"  -> 🚫 Descartado por estado final."); conn = db_conn.conectar_db(); cursor = conn.cursor(); cursor.execute("UPDATE trabajos SET estado_odoo = 'DESCARTADO_ESTADO_FINAL' WHERE order_code = ?", (order_code,)); conn.commit(); conn.close(); continue

        try:
            cliente_id = buscar_cliente_existente(odoo_api, grupo[0])
            if not cliente_id: continue
            conn = db_conn.conectar_db(); cursor = conn.cursor(); cursor.execute("UPDATE trabajos SET odoo_partner_id = ? WHERE order_code = ?", (cliente_id, order_code)); conn.commit(); conn.close()
            
            oportunidad_id = crear_oportunidad(odoo_api, grupo[0], cliente_id)
            if not oportunidad_id: continue
            conn = db_conn.conectar_db(); cursor = conn.cursor(); cursor.execute("UPDATE trabajos SET odoo_opportunity_id = ? WHERE order_code = ?", (oportunidad_id, order_code)); conn.commit(); conn.close()

            cf_id, ce_id = (None, None)
            if grupo[0].get('channel') == mapeos.MERCADOLIBROS_CHANNEL_ID: cf_id, ce_id = gestionar_contacto_mercadolibros(odoo_api, grupo[0])
            
            so_id = crear_pedido_venta(odoo_api, grupo, cliente_id, oportunidad_id, cf_id, ce_id, analytic_accounts)
            if so_id:
                so_record = odoo_api.env['sale.order'].browse(so_id); 
                so_name = so_record.name
                lineas_odoo = so_record.order_line.read(['id', 'x_bmg_order_line'])
                mapa = {line['x_bmg_order_line']: line['id'] for line in lineas_odoo if line.get('x_bmg_order_line')}
                ups = [(so_id, so_name, mapa.get(t['line_number']), order_code, t['line_number']) for t in grupo if t['line_number'] in mapa]
                if ups: conn = db_conn.conectar_db(); cursor = conn.cursor(); cursor.executemany("UPDATE trabajos SET odoo_sale_order_id = ?, odoo_sale_order_name = ?, odoo_sale_order_line_id = ? WHERE order_code = ? AND line_number = ?", ups); conn.commit(); conn.close()

        except Exception as e: print(f"  -> ❌ ERROR FATAL {order_code}: {e}")

if __name__ == "__main__":
    run()
