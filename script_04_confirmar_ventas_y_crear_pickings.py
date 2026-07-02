import json
from datetime import datetime, timedelta

# Importar módulos comunes de la V2.0
from common import mapeos, db_conn, odoo_conn, meli_api
from common.notificador import enviar_email # Importar el notificador
import common.bmg_estados_mapeo as bmg_estados_mapeo
import logging

_logger = logging.getLogger(__name__)

# --- FUNCIONES DE AYUDA PARA INTERACCIONES CON ODOO ---

def _update_opportunity_stage(odoo_api, opportunity_id, stage_name):
    """Actualiza la etapa de una oportunidad en Odoo."""
    if not opportunity_id:
        print(f"WARNING: No se puede actualizar la etapa de la oportunidad: opportunity_id es None.")
        return False
    try:
        opportunity = odoo_api.env['crm.lead'].browse(opportunity_id)
        if not opportunity:
            print(f"WARNING: Oportunidad con ID {opportunity_id} no encontrada en Odoo.")
            return False
        
        stage_ids = odoo_api.env['crm.stage'].search([('name', '=', stage_name)], limit=1)
        if not stage_ids:
            print(f"ERROR: Etapa '{stage_name}' no encontrada en Odoo CRM.")
            return False
        stage = odoo_api.env['crm.stage'].browse(stage_ids[0]) # Browse the first ID to get the record
        
        if opportunity.stage_id.id != stage.id:
            opportunity.write({'stage_id': stage.id})
            print(f"INFO: Oportunidad {opportunity_id} movida a la etapa '{stage_name}'.")
        else:
            print(f"INFO: Oportunidad {opportunity_id} ya está en la etapa '{stage_name}'.")
        return True
    except Exception as e:
        print(f"ERROR: Error al actualizar la etapa de la oportunidad {opportunity_id} a '{stage_name}': {e}")
        return False

# --- FUNCIONES COPIADAS Y ADAPTADAS ---

def _es_estado_confirmable(line_status_id):
    """
    Verifica si el estado de la línea BMG (LineStatusId) permite la confirmación
    en Odoo, usando la lista centralizada en mapeos.
    """
    try:
        status_id = int(line_status_id)
        return status_id not in mapeos.ESTADOS_NO_CONFIRMABLES_IDS
    except (ValueError, TypeError):
        return False

def _obtener_o_crear_contacto_envio(odoo_api, cliente_principal_id, envio_data):
    """
    Busca o crea un contacto de envío como entidad independiente (suelto).
    Se eliminó la dependencia de parent_id para probar si Odoo permite pickings sueltos.
    """
    partner_model = odoo_api.env['res.partner']
    nombre_contacto = envio_data.get('Contacto', mapeos.ODOO_CONTACT_DEFAULT_NAME).strip()
    direccion_calle = envio_data.get('Direccion', '').strip()
    
    # Buscamos el contacto por nombre y dirección, sin importar quién sea el padre
    partner_ids = partner_model.search([
        ('type', '=', mapeos.ODOO_PARTNER_TYPE_DELIVERY),
        ('street', '=', direccion_calle),
        ('name', '=', nombre_contacto)
    ])
    
    if partner_ids:
        print(f"    - 👤 Contacto de envío existente encontrado (Suelto): ID {partner_ids[0]}.")
        return partner_ids[0]

    print(f"    - 🆕 Creando nuevo contacto de envío SUELTO para: {nombre_contacto}")
    new_partner_vals = {
        'name': nombre_contacto, 
        'type': mapeos.ODOO_PARTNER_TYPE_DELIVERY,
        'street': direccion_calle, 
        'street2': envio_data.get('Destino', '').strip(),
        'city': envio_data.get('Ciudad', '').strip(), 
        'zip': envio_data.get('ZIPCode', '').strip(),
        'country_id': partner_model.browse([cliente_principal_id]).country_id.id,
        'phone': envio_data.get('Telefono', '').strip(), 
        'email': envio_data.get('Email', '').strip()
    }
    
    try:
        new_partner_id = partner_model.create(new_partner_vals)
        print(f"    ✅ Contacto de envío suelto '{nombre_contacto}' creado con ID: {new_partner_id}.")
        return new_partner_id
    except Exception as e:
        print(f"    ❌ Error al crear contacto de envío suelto en Odoo: {e}")
        return None

def _calcular_fecha_entrega_edist(order_date_str):
    """
    Calcula la fecha de entrega programada para pedidos eDist.
    Copiado 1:1 del original.
    """
    try:
        order_date = datetime.strptime(order_date_str, '%Y%m%d')
        reglas_desplazamiento = mapeos.EDIST_DELIVERY_RULES
        day_of_week = order_date.weekday()
        days_to_add = reglas_desplazamiento.get(day_of_week, 0)
        if day_of_week == 2: days_to_add = mapeos.EDIST_DELIVERY_RULE_OVERRIDE_WEDNESDAY
        elif day_of_week == 5: days_to_add = mapeos.EDIST_DELIVERY_RULE_OVERRIDE_SATURDAY
        return (order_date + timedelta(days=days_to_add)).strftime('%Y-%m-%d')
    except (ValueError, KeyError, TypeError):
        return False





def generar_transferencias_envio_odoo(odoo_api, so_id, cliente_principal_id, datos_envio_json, grupo_trabajos):
    """
    Crea pickings por cada instrucción de envío.
    MODIFICADO: Devuelve una estructura de datos con todos los IDs creados.
    """
    picking_model = odoo_api.env['stock.picking']
    so_model = odoo_api.env['sale.order']
    
    sale_order = so_model.browse([so_id])
    so_name = sale_order.name
    
    # --- CHECK FOR EXISTING PICKINGS ---
    existing_pickings = picking_model.search([('sale_id', '=', so_id), ('state', '!=', 'cancel')])
    if existing_pickings:
        print(f"    -> ℹ️ Ya existen {len(existing_pickings)} pickings para el pedido {so_name}. Omitiendo creación de pickings duplicados.")
        # Retornamos data simulada o los IDs existentes para que el script no falle
        existing_data = []
        for pick_id in existing_pickings:
            existing_data.append({
                'picking_id': pick_id,
                'shipping_partner_id': False, # Not strictly needed if they already exist
                'move_ids': []
            })
        return existing_data
    # -----------------------------------

    picking_type_ids = odoo_api.env['stock.picking.type'].search([
        ('code', '=', mapeos.ODOO_PICKING_TYPE_CODE_OUTGOING), ('warehouse_id.company_id', '=', sale_order.company_id.id)
    ], limit=1)

    if not so_name or not picking_type_ids:
        print("  ❌ Error: No se pudo encontrar el Pedido de Venta o el Tipo de Picking de salida."); return []
        
    picking_type_record = odoo_api.env['stock.picking.type'].browse(picking_type_ids[0]) 
    location_id = picking_type_record.default_location_src_id.id 
    picking_type_id_final = picking_type_record.id 

    title_to_sol_map = {t['title_id']: t.get('odoo_sale_order_line_id') for t in grupo_trabajos if t.get('title_id')}
    title_to_variant_map = {t['title_id']: t.get('odoo_product_variant_id') for t in grupo_trabajos}
    
    # --- NUEVO: Mapeo de variante a descripción para las líneas de movimiento ---
    variant_to_desc_map = {t['odoo_product_variant_id']: t.get('descripcion_detalle_libro', '') for t in grupo_trabajos}
    
    datos_envio = json.loads(datos_envio_json)
    pickings_data = []
    
    for idx, envio in enumerate(datos_envio, 1):
        contacto_envio_id = _obtener_o_crear_contacto_envio(odoo_api, cliente_principal_id, envio)
        if not contacto_envio_id: continue
            
        move_lines = []
        peso_total_envio_gramos = 0
        for titulo in envio.get('Titulos', []):
            title_id_json = titulo.get('TitleId')
            copies = int(titulo.get('Copies', 0))
            variant_id = title_to_variant_map.get(title_id_json)
            sale_line_id = title_to_sol_map.get(title_id_json)
            
            # Sumar peso de BMG (viene en gramos)
            try:
                peso_linea = float(titulo.get('TotalWeight', 0))
                peso_total_envio_gramos += peso_linea
            except: pass

            if copies > 0 and variant_id and sale_line_id:
                # --- NUEVO: Descripción para la línea de movimiento ---
                descripcion_completa = variant_to_desc_map.get(variant_id, '')
                lineas = descripcion_completa.strip().split('\n')
                descripcion_resumida = "\n".join(lineas[:2]).strip()
                # --- FIN NUEVO ---

                move_lines.append((0, 0, {
                    'name': so_name, 
                    'product_id': variant_id, 
                    'product_uom_qty': copies,
                    'description_picking': descripcion_resumida, # AÑADIDO A stock.move
                    'product_uom': odoo_api.env.ref(mapeos.ODOO_UOM_PRODUCT_UOM_UNIT_XMLID).id,
                    'location_id': location_id, 
                    'location_dest_id': odoo_api.env.ref(mapeos.ODOO_LOCATION_CUSTOMERS_XMLID).id,
                    'partner_id': contacto_envio_id, 
                    'sale_line_id': sale_line_id,
                }))
        
        if not move_lines: continue
            
        trabajo_cabecera = grupo_trabajos[0]
        fecha_programada = False
        if mapeos.BMG_ORDER_TYPE_EDIST_GENERIC in trabajo_cabecera.get('order_type', ''):
            fecha_programada = _calcular_fecha_entrega_edist(trabajo_cabecera.get('order_date'))
        elif trabajo_cabecera.get('delivery_date') and len(trabajo_cabecera.get('delivery_date')) == 8:
            try: fecha_programada = datetime.strptime(trabajo_cabecera.get('delivery_date'), '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError: pass

        fecha_con_hora = f"{fecha_programada} {mapeos.ODOO_SCHEDULED_TIME}" if fecha_programada else False
        
        # Convertir a Kg para Odoo
        peso_total_kg = peso_total_envio_gramos / 1000.0
        observaciones_bmg = envio.get('DestinationObservations', mapeos.ODOO_SHIPPING_NOTE_DEFAULT)
        nota_picking = f"Instrucción de Envío #{idx}: {observaciones_bmg}\n\n[BMG] Peso Estimado Total: {peso_total_kg} Kg"

        # Buscar Shipment ID si es de Mercado Libre
        shipment_id = None
        is_meli_delivery = False
        
        empresa_raw = envio.get('Empresa', '')
        es_canal_meli = str(trabajo_cabecera.get('channel', '')) == '236'
        
        if es_canal_meli and 'MELI-' in empresa_raw.upper():
            # Extraer meli_order_id desde el campo Empresa del JSON de envío
            meli_order_id = empresa_raw.upper().replace('MELI-', '').strip()
            meli_data = meli_api.obtener_detalle_orden_ml(meli_order_id)
            if meli_data:
                raw_ship_id = meli_data.get('raw_data', {}).get('shipping', {}).get('id')
                if raw_ship_id:
                    shipment_id = str(raw_ship_id)
                    is_meli_delivery = True  # Solo si hay un ID real de envío

        picking_vals = {
            'picking_type_id': picking_type_id_final, 'partner_id': contacto_envio_id,
            'origin': so_name, 
            'note': nota_picking,
            'move_ids_without_package': move_lines, 
            'sale_id': so_id,
            'scheduled_date': fecha_con_hora, 
            'date_deadline': fecha_con_hora,
            'shipping_weight': peso_total_kg,
            'x_meli_shipment_id': shipment_id, 
            'x_is_meli_delivery': is_meli_delivery, # Bandera protegida
            # 'x_is_bmg_picking': True, # Se moverá al write para mayor fiabilidad
        }        
        try:
            new_picking_id = picking_model.create(picking_vals)
            
            # Se escribe el sale_id y el flag BMG en un solo llamado para asegurar la atomicidad
            picking_model.write([new_picking_id], {
                'sale_id': so_id,
                'x_is_bmg_picking': True
            })

            new_picking_record = picking_model.browse(new_picking_id)
            move_ids = new_picking_record.move_ids_without_package.ids
            print(f"  ✅ Transferencia de Envío #{idx} creada: {new_picking_record.name}")
            pickings_data.append({
                'picking_id': new_picking_id,
                'shipping_partner_id': contacto_envio_id,
                'move_ids': move_ids
            })
        except Exception as e:
            print(f"  🔥🔥🔥 ERROR DETALLADO AL CREAR TRANSFERENCIA #{idx}: {e} 🔥🔥🔥"); return []
            
    return pickings_data

def run():
    print(f"--- Iniciando Script 4: Confirmar Ventas y Crear Pickings [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    conn = db_conn.conectar_db()
    if not conn: return
    cursor = conn.cursor()
    
    # --- MODO DE PRUEBA: Filtrar por TEST_ORDER_CODE si está definido ---
    if mapeos.TEST_ORDER_CODE:
        _logger.info(f"  -> MODO DE PRUEBA: Procesando únicamente el pedido {mapeos.TEST_ORDER_CODE}")
        cursor.execute("""
            SELECT *, MAX(odoo_opportunity_id) as odoo_opportunity_id_agg FROM trabajos 
            WHERE order_code = ?
            GROUP BY order_code
        """, (mapeos.TEST_ORDER_CODE,))
    else:
        cursor.execute("""
            SELECT *, MAX(odoo_opportunity_id) as odoo_opportunity_id_agg FROM trabajos 
            WHERE odoo_sale_order_id IS NOT NULL AND odoo_pickings_data_json IS NULL
            GROUP BY order_code
        """)
    
    pedidos_a_confirmar = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not pedidos_a_confirmar:
        print("No hay pedidos pendientes de confirmación y creación de pickings."); return

    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        asunto = "Error Crítico en Script 04: Conexión a Odoo fallida"
        cuerpo = "El Script 04 no pudo establecer conexión con Odoo. Revise la configuración."
        enviar_email(asunto, cuerpo)
        return

    print(f"Se encontraron {len(pedidos_a_confirmar)} pedidos para procesar.")
    

    for pedido_cabecera in pedidos_a_confirmar:
        order_code = pedido_cabecera['order_code']
        so_id = pedido_cabecera['odoo_sale_order_id']
        partner_id = pedido_cabecera['odoo_partner_id']
        print(f"\n--- Procesando Pedido: {order_code} (SO ID: {so_id}) ---")

        try: # Main try block for each order
            if not _es_estado_confirmable(pedido_cabecera['line_status_id']):
                print(f"  -> ℹ️ Pedido {order_code} (SO ID: {so_id}) no está en un estado BMG confirmable (Estado BMG: {pedido_cabecera['line_status_id']}). Saltando.")
                continue
            
            if not partner_id:
                mensaje_error = f"El pedido {order_code} (SO ID: {so_id}) no tiene un ID de cliente principal (odoo_partner_id) guardado. Saltando."
                asunto = f"Error Script 04: Pedido {order_code} sin Partner ID"
                enviar_email(asunto, mensaje_error)
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    so_record.message_post(body=mensaje_error, message_type=mapeos.CHATTER_MESSAGE_TYPE_COMMENT, subtype_xmlid=mapeos.CHATTER_SUBTYPE_XMLID_NOTE)
                except Exception as chat_e:
                    print(f"  -> ❌ Error al publicar en Chatter para SO ID {so_id}: {chat_e}")
                continue

            conn = db_conn.conectar_db(); cursor = conn.cursor()
            cursor.execute("SELECT * FROM trabajos WHERE order_code = ?", (order_code,)); grupo_trabajos = [dict(row) for row in cursor.fetchall()]; conn.close()
            if not grupo_trabajos:
                mensaje_error = f"No se encontraron líneas de trabajo en la DB local para el pedido {order_code} (SO ID: {so_id}). Saltando."
                asunto = f"Error Script 04: Pedido {order_code} sin líneas de trabajo"
                enviar_email(asunto, mensaje_error)
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    so_record.message_post(body=mensaje_error, message_type=mapeos.CHATTER_MESSAGE_TYPE_COMMENT, subtype_xmlid=mapeos.CHATTER_SUBTYPE_XMLID_NOTE)
                except Exception as chat_e:
                    print(f"  -> ❌ Error al publicar en Chatter para SO ID {so_id}: {chat_e}")
                continue

            print(f"  -> Creando transferencias de stock (pickings)...")
            pickings_data = generar_transferencias_envio_odoo(
                odoo_api, so_id, partner_id,
                pedido_cabecera['datos_envio_json'], grupo_trabajos
            )

            if not pickings_data:
                mensaje_error = f"No se pudieron crear los pickings para el pedido {order_code} (SO ID: {so_id}). El pedido no se confirmará."
                asunto = f"Error Script 04: No se crearon pickings para pedido {order_code}"
                enviar_email(asunto, mensaje_error)
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    so_record.message_post(body=mensaje_error, message_type=mapeos.CHATTER_MESSAGE_TYPE_COMMENT, subtype_xmlid=mapeos.CHATTER_SUBTYPE_XMLID_NOTE)
                except Exception as chat_e:
                    print(f"  -> ❌ Error al publicar en Chatter para SO ID {so_id}: {chat_e}")
                continue            
            print(f"  -> Confirmando Pedido de Venta SO ID: {so_id}...")
            odoo_api.env['sale.order'].browse([so_id]).action_confirm()
            print(f"  -> ✅ Pedido {order_code} confirmado en Odoo.")

            # --- LÓGICA DE FACTURACIÓN AUTOMÁTICA PARA MERCADO LIBRE ---
            if mapeos.ML_FACTURACION_AUTOMATICA:
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    # Verificar si es un pedido de Mercado Libre (por el canal del partner)
                    es_meli = False
                    if so_record.partner_id.x_channel_id == mapeos.MERCADOLIBROS_CHANNEL_ID:
                        es_meli = True
                    
                    if es_meli:
                        print(f"  -> 📄 Generando factura automática para pedido de Mercado Libre {so_record.name}...")
                        # 1. Crear la factura
                        invoice_ids = so_record._create_invoices()
                        if invoice_ids:
                            # invoice_ids suele ser un recordset o lista de IDs en odoorpc
                            invoices = odoo_api.env['account.move'].browse(invoice_ids)
                            for inv in invoices:
                                # 2. Validar (confirmar) la factura
                                inv.action_post()
                                print(f"  -> ✅ Factura {inv.name} creada y validada automáticamente.")
                                
                            msg_factura = f"✅ **Facturación Automática ML:** Se ha creado y validado la factura {', '.join(invoices.mapped('name'))} automáticamente."
                            
                            # --- NUEVA LÓGICA: REGISTRAR PAGO SI ESTÁ PAGO EN ML ---
                            try:
                                # Leemos el estado directamente de la DB (ya está en pedido_cabecera)
                                m_status = pedido_cabecera.get('meli_status')
                                
                                if m_status == 'paid':
                                    print(f"  -> 💳 Registrando pago en Odoo (Estado ML: {m_status})...")
                                    journal_ids = odoo_api.env['account.journal'].search([('name', '=', mapeos.ODOO_JOURNAL_MERCADOPAGO)], limit=1)
                                    if journal_ids:
                                        # Usar el wizard de registro de pago
                                        ctx = {'active_model': 'account.move', 'active_ids': invoice_ids}
                                        wizard_vals = {
                                            'journal_id': journal_ids[0],
                                            'payment_date': datetime.now().strftime('%Y-%m-%d'),
                                            'communication': invoices[0].name # Usamos el nombre de la primera factura como Memo
                                        }
                                        wizard = odoo_api.env['account.payment.register'].with_context(ctx).create(wizard_vals)
                                        wizard.action_create_payments()
                                        print(f"  -> ✅ Pago registrado y conciliado en diario {mapeos.ODOO_JOURNAL_MERCADOPAGO}.")
                                        msg_factura += f"\n💳 **Pago Registrado:** Se concilió el pago automáticamente en el diario {mapeos.ODOO_JOURNAL_MERCADOPAGO}."
                                    else:
                                        print(f"  -> ⚠️ Diario '{mapeos.ODOO_JOURNAL_MERCADOPAGO}' no encontrado. No se registró el pago.")
                                elif m_status:
                                    print(f"  -> ℹ️ La orden en ML tiene estado '{m_status}', no se registra pago automático.")
                            except Exception as e_pago:
                                _logger.error(f"  -> ❌ Error al registrar pago automático: {e_pago}")
                                msg_factura += f"\n⚠️ **Error Pago:** No se pudo registrar el pago automáticamente: {str(e_pago)}"
                            
                            so_record.message_post(body=msg_factura, message_type='comment', subtype_xmlid=mapeos.CHATTER_SUBTYPE_XMLID_NOTE)
                        else:
                            print(f"  -> ⚠️ No se pudo crear la factura para {so_record.name} (posiblemente ya facturado o sin líneas facturables).")
                except Exception as e_fact:
                    _logger.error(f"  -> ❌ Error en facturación automática ML para {order_code}: {e_fact}")
                    try:
                        odoo_api.env['sale.order'].browse(so_id).message_post(
                            body=f"❌ **Error Facturación Automática ML:** {str(e_fact)}", 
                            message_type='comment', 
                            subtype_xmlid=mapeos.CHATTER_SUBTYPE_XMLID_NOTE
                        )
                    except: pass
            # --- FIN LÓGICA FACTURACIÓN AUTOMÁTICA ---

            # --- NUEVA LÓGICA: Buscar tarea auto-generada y actualizar su descripción ---
            if mapeos.PRODUCCION_ACTIVADA:
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    # Buscar la línea de pedido de validación
                    validation_line = None
                    for line in so_record.order_line:
                        if line.product_id.name == 'Validación de diseños del cliente':
                            validation_line = line
                            break
                    
                    if validation_line and validation_line.task_id:
                        task_id = validation_line.task_id.id
                        _logger.info(f"  -> Tarea de validación auto-generada encontrada con ID: {task_id}")
                        
                        # Asumimos que la descripción y el nombre del libro provienen de la primera línea de libro encontrada.
                        trabajo_de_referencia = None
                        for trabajo in grupo_trabajos:
                            if trabajo.get('descripcion_detalle_libro'):
                                trabajo_de_referencia = trabajo
                                break

                        if trabajo_de_referencia:
                            # Construir el nuevo nombre y la descripción para la tarea
                            nuevo_nombre_tarea = f"{mapeos.TASK_NAME_PREFIX_VALIDACION_DISENO}{trabajo_de_referencia['order_code']}-{trabajo_de_referencia['line_number']}"
                            descripcion_html = trabajo_de_referencia['descripcion_detalle_libro'].replace('\n', '<br>')

                            # Preparar los valores para la actualización inicial de la tarea
                            write_vals = {
                                'name': nuevo_nombre_tarea,
                                'description': descripcion_html,
                                'x_bmg_order_line': trabajo_de_referencia['line_number'],
                            }

                            # Actualizar la tarea en Odoo con sus datos de BMG
                            odoo_api.env['project.task'].browse(task_id).write(write_vals)
                            _logger.info(f"  -> ✅ Tarea {task_id} actualizada con nombre y descripción.")

                            # Guardar el ID de la tarea en la DB local para futuras referencias
                            try:
                                conn_task = db_conn.conectar_db()
                                if conn_task:
                                    cursor_task = conn_task.cursor()
                                    cursor_task.execute(
                                        "UPDATE trabajos SET odoo_project_task_id = ? WHERE order_code = ?",
                                        (task_id, trabajo_de_referencia['order_code'])
                                    )
                                    conn_task.commit()
                                    conn_task.close()
                                    _logger.info(f"  -> 💾 ID de tarea {task_id} guardado en la DB local para el pedido {trabajo_de_referencia['order_code']}.")
                                else:
                                    _logger.error(f"  -> ❌ No se pudo conectar a la DB local para guardar el ID de la tarea {task_id}.")
                            except Exception as db_err:
                                _logger.error(f"  -> ❌ Error al guardar el ID de la tarea {task_id} en la DB local: {db_err}")


                        else:
                            _logger.warning(f"  -> ⚠️ No se encontró la descripción del libro en la DB local para actualizar la tarea {task_id}.")
                    elif validation_line:
                        _logger.warning(f"  -> ⚠️ Se encontró la línea de validación, pero Odoo aún no ha generado la tarea asociada (task_id está vacío).")
                    else:
                        _logger.info("  -> ℹ️ No se encontró línea de validación en este pedido, no se actualiza ninguna tarea.")

                except Exception as e:
                    _logger.error(f"  -> ❌ Error al intentar buscar y actualizar la tarea de proyecto: {e}")
            # --- FIN NUEVA LÓGICA ---

            # Nuevo: Verificar y mover la Oportunidad a "Ganado con OT"
            opportunity_id = pedido_cabecera.get('odoo_opportunity_id_agg') # Usar el ID agregado
            if opportunity_id:
                _update_opportunity_stage(odoo_api, opportunity_id, "Ganado con OT")
            else:
                print(f"  -> WARNING: No se encontró odoo_opportunity_id para el pedido {order_code}. No se pudo actualizar la etapa de la oportunidad.")

            conn = db_conn.conectar_db(); cursor = conn.cursor()
            pickings_json = json.dumps(pickings_data)
            cursor.execute("UPDATE trabajos SET odoo_pickings_data_json = ? WHERE order_code = ?", (pickings_json, order_code))
            conn.commit(); conn.close()
            print(f"  -> 💾 Datos de pickings guardados en la base de datos para {order_code}.")

        except Exception as e:
            error_str = str(e).lower()
            # Palabras clave para identificar un error de estado (ej. ya confirmado)
            is_state_error = 'state' in error_str and ('confirm' in error_str or 'valid' in error_str)
            
            if is_state_error:
                print(f"  -> ℹ️ Pedido {order_code} (SO ID: {so_id}) ya estaba confirmado de antemano. El proceso continúa como si fuera exitoso.")
                
                # --- Se repite la lógica de éxito aquí para asegurar la consistencia de los datos ---
                opportunity_id = pedido_cabecera.get('odoo_opportunity_id_agg')
                if opportunity_id:
                    _update_opportunity_stage(odoo_api, opportunity_id, "Ganado con OT")
                else:
                    print(f"  -> WARNING: No se encontró odoo_opportunity_id para el pedido {order_code}. No se pudo actualizar la etapa de la oportunidad.")

                conn = db_conn.conectar_db()
                if conn:
                    cursor = conn.cursor()
                    # 'pickings_data' fue definido en el bloque 'try' principal y está disponible aquí
                    pickings_json = json.dumps(pickings_data)
                    cursor.execute("UPDATE trabajos SET odoo_pickings_data_json = ? WHERE order_code = ?", (pickings_json, order_code))
                    conn.commit()
                    conn.close()
                    print(f"  -> 💾 Datos de pickings guardados en la base de datos para {order_code} (confirmación manejada).")

            else:
                # Es un error genuinamente inesperado, se maneja como antes
                mensaje_error = f"Ocurrió un error fatal no controlado al procesar la confirmación del pedido {order_code} (SO ID: {so_id}).\n\nError:\n{str(e)}"
                asunto = f"Error INESPERADO en Script 04 para pedido {order_code}"
                enviar_email(asunto, mensaje_error)
                try:
                    so_record = odoo_api.env['sale.order'].browse(so_id)
                    so_record.message_post(body=mensaje_error, message_type='comment', subtype_xmlid='mail.mt_note')
                except Exception as chat_e:
                    print(f"  -> ❌ Error al publicar en Chatter para SO ID {so_id}: {chat_e}")

    print("--- Script 4 Finalizado ---")

if __name__ == "__main__":
    run()