# -*- coding: utf-8 -*-
"""
Script 2: Actualizador de Estados desde BMG.

- Lee la base de datos local para encontrar pedidos en curso (no entregados/facturados).
- Para cada pedido en curso, consulta la API de BMG para obtener su estado más reciente.
- Actualiza las columnas `line_status` y `line_status_id` en la base de datos local.
"""

from datetime import datetime
from zeep import Client
import logging # Asegurarse de que logging esté importado

# Importar módulos comunes de la V2.0
from common import mapeos, db_conn, odoo_conn
from common.notificador import enviar_email
import common.bmg_estados_mapeo as bmg_estados_mapeo # Nuevo: Mapeo de estados BMG

# from odoo.exceptions import MissingError # Nuevo: Para manejar errores de Odoo

_logger = logging.getLogger(__name__) # Inicializar logger

# --- FUNCIONES DE AYUDA PARA INTERACCIONES CON ODOO ---

def _update_opportunity_stage(odoo_api, opportunity_id, stage_name):
    """Actualiza la etapa de una oportunidad en Odoo."""
    if not opportunity_id:
        _logger.warning(f"No se puede actualizar la etapa de la oportunidad: opportunity_id es None.")
        return False
    try:
        opportunity = odoo_api.env['crm.lead'].browse(opportunity_id)
        if not opportunity.exists():
            _logger.warning(f"Oportunidad con ID {opportunity_id} no encontrada en Odoo.")
            return False
        
        stage_ids = odoo_api.env['crm.stage'].search([('name', '=', stage_name)], limit=1)
        if not stage_ids:
            _logger.error(f"Etapa '{stage_name}' no encontrada en Odoo CRM.")
            return False
        stage_id = stage_ids[0]
        
        if opportunity.stage_id.id != stage_id:
            opportunity.write({'stage_id': stage_id})
            _logger.info(f"Oportunidad {opportunity_id} movida a la etapa '{stage_name}'.")
        else:
            _logger.info(f"Oportunidad {opportunity_id} ya está en la etapa '{stage_name}'.")
        return True
    except Exception as e:
        _logger.error(f"Error al actualizar la etapa de la oportunidad {opportunity_id} a '{stage_name}': {e}")
        return False

def _create_activity(odoo_api, res_id, res_model, summary, user_id=None, date_deadline=None):
    """Crea una actividad programada en Odoo."""
    try:
        activity_vals = {
            'res_id': res_id,
            'res_model_id': odoo_api.env['ir.model']._get(res_model).id,
            'summary': summary,
            'activity_type_id': odoo_api.env['mail.activity.type'].search([('name', '=', mapeos.ODOO_ACTIVITY_TYPE_TODO)], limit=1).id, # Tipo de actividad 'To Do'
            'date_deadline': date_deadline if date_deadline else (datetime.now() + timedelta(days=mapeos.ODOO_ACTIVITY_DEADLINE_DAYS)).strftime('%Y-%m-%d'),
        }
        if user_id:
            activity_vals['user_id'] = user_id
        
        new_activity_id = odoo_api.env['mail.activity'].create(activity_vals)
        _logger.info(f"Actividad '{summary}' creada para {res_model} ID {res_id}. ID Actividad: {new_activity_id.id}")
        return new_activity_id.id
    except Exception as e:
        _logger.error(f"Error al crear actividad '{summary}' para {res_model} ID {res_id}: {e}")
        return None

def _mark_activity_done(odoo_api, res_id, res_model, summary_to_find):
    """Marca una actividad como realizada en Odoo."""
    try:
        model_ids = odoo_api.env['ir.model'].search([('model', '=', res_model)], limit=1)
        if not model_ids:
            _logger.error(f"No se pudo encontrar el modelo '{res_model}' en Odoo.")
            return False
        model_id = model_ids[0]
        
        activity_ids = odoo_api.env['mail.activity'].search([
            ('res_id', '=', res_id),
            ('res_model_id', '=', model_id),
            ('summary', 'ilike', summary_to_find),
            ('state', 'in', ['overdue', 'today']) # Actividades pendientes o vencidas
        ], limit=1)
        
        if activity_ids:
            activity_to_mark = odoo_api.env['mail.activity'].browse(activity_ids[0])
            activity_to_mark.action_done()
            _logger.info(f"Actividad '{summary_to_find}' para {res_model} ID {res_id} marcada como realizada.")
            return True
        else:
            _logger.info(f"No se encontró actividad pendiente '{summary_to_find}' para {res_model} ID {res_id}.")
            return False
    except Exception as e:
        _logger.error(f"Error al marcar actividad '{summary_to_find}' como realizada para {res_model} ID {res_id}: {e}")
        return False

def _create_bmg_notification(odoo_api, order_code, order_line_number, bmg_state_id, project_task_id=None):
    """
    Crea un registro en bmg.notification.queue para enviar un estado a BMG.
    Esta función es más flexible y no requiere una mrp.workorder.
    """
    try:
        queue_vals = {
            'order_code': order_code,
            'order_line': order_line_number,
            'bmg_state_id': bmg_state_id,
            'state': 'pending',
        }
        if project_task_id:
            queue_vals['project_task_id'] = project_task_id

        new_queue_record = odoo_api.env['bmg.notification.queue'].create(queue_vals)
        _logger.info(f"Registro en bmg.notification.queue creado para Pedido BMG {order_code}-{order_line_number}, Estado BMG: {bmg_state_id}. ID: {new_queue_record.id}")
        return new_queue_record.id
    except Exception as e:
        _logger.error(f"Error al crear registro en bmg.notification.queue para Pedido BMG {order_code}-{order_line_number}, Estado BMG {bmg_state_id}: {e}")
        return None

def _move_project_task_stage(odoo_api, project_task_id, stage_name):
    """Mueve una tarea de proyecto a una etapa específica en Odoo."""
    if not project_task_id:
        _logger.warning(f"No se puede mover la etapa de la tarea de proyecto: project_task_id es None.")
        return False
    try:
        task = odoo_api.env['project.task'].browse(project_task_id)
        if not task:
            _logger.warning(f"Tarea de proyecto con ID {project_task_id} no encontrada en Odoo.")
            return False
        
        stage_ids = odoo_api.env['project.task.type'].search([('name', '=', stage_name), ('project_ids', 'in', [task.project_id.id])], limit=1)
        if not stage_ids:
            _logger.error(f"Etapa '{stage_name}' no encontrada para el proyecto de la tarea {project_task_id}.")
            return False
        
        stage_id = stage_ids[0]
        if task.stage_id.id != stage_id:
            task.write({'stage_id': stage_id})
            _logger.info(f"Tarea de proyecto {project_task_id} movida a la etapa '{stage_name}'.")
        else:
            _logger.info(f"Tarea de proyecto {project_task_id} ya está en la etapa '{stage_name}'.")
        return True
    except Exception as e:
        _logger.error(f"Error al mover la tarea de proyecto {project_task_id} a la etapa '{stage_name}': {e}")
        return False

def _archive_project_task(odoo_api, project_task_id):
    """Archiva una tarea de proyecto en Odoo."""
    if not mapeos.PRODUCCION_ACTIVADA:
        _logger.info(f"Archivado de tarea de proyecto OMITIDO (Toggle producción desactivado).")
        return False
    if not project_task_id:
        _logger.warning(f"No se puede archivar la tarea de proyecto: project_task_id es None.")
        return False
    try:
        task = odoo_api.env['project.task'].browse(project_task_id)
        if not task:
            _logger.warning(f"Tarea de proyecto con ID {project_task_id} no encontrada en Odoo.")
            return False
        
        if not task.active:
            _logger.info(f"Tarea de proyecto {project_task_id} ya está archivada.")
            return True

        task.write({'active': False})
        _logger.info(f"Tarea de proyecto {project_task_id} archivada con éxito.")
        return True
    except Exception as e:
        _logger.error(f"Error al archivar la tarea de proyecto {project_task_id}: {e}")
        return False

def run():
    """
    Función principal del script.
    """
    _logger.info(f"--- Iniciando Script 2: Actualización de Estados desde BMG [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")

    # Asegurarse de que la DB esté inicializada
    db_conn.inicializar_db()

    # 1. Obtener pedidos no finalizados de la DB local
    pedidos_a_verificar = []
    
    # --- MODO DE PRUEBA: Filtrar por TEST_ORDER_CODE si está definido ---
    if mapeos.TEST_ORDER_CODE:
        _logger.info(f"  -> MODO DE PRUEBA: Verificando únicamente el pedido {mapeos.TEST_ORDER_CODE}")
        pedidos_a_verificar = [mapeos.TEST_ORDER_CODE]
    else:
        try:
            conn = db_conn.conectar_db()
            if not conn:
                asunto = "Error Crítico en Script 02: Conexión a DB local fallida"
                cuerpo = "El Script 02 no pudo establecer conexión con la base de datos local. Revise la configuración."
                enviar_email(asunto, cuerpo)
                return
            cursor = conn.cursor()
            
            # Usar la lista centralizada de estados finales (Entregado, Facturado, Anulado)
            ids_finales_unicos = bmg_estados_mapeo.LISTA_ESTADOS_FINALES_IDS
            
            # Crear los placeholders para la consulta SQL de forma dinámica
            placeholders = ', '.join('?' for _ in ids_finales_unicos)
            
            # Seleccionar pedidos cuyo estado NO SEA final (o sea nulo)
            query = f"SELECT DISTINCT order_code FROM trabajos WHERE line_status_id IS NULL OR line_status_id NOT IN ({placeholders})"
            print(f"DEBUG: Executing query: {query} with parameters: {ids_finales_unicos}") # Added debug print
            cursor.execute(query, ids_finales_unicos)
            pedidos_a_verificar = [row['order_code'] for row in cursor.fetchall()]
            conn.close()
            
            if not pedidos_a_verificar:
                print("No se encontraron pedidos activos para verificar estados. Proceso finalizado.")
                return
                
            print(f"Se encontraron {len(pedidos_a_verificar)} pedidos activos para verificar su estado.")
        except Exception as e:
            print(f"❌ Error durante la lectura de pedidos de DB local: {e}")
            asunto = "Error Crítico en Script 02: Lectura de pedidos de DB local fallida"
            cuerpo = f"El Script 02 falló al leer los pedidos de la base de datos local.\n\nError:\n{str(e)}"
            enviar_email(asunto, cuerpo)
            return

    # 2. Conectar a la API de BMG
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        _logger.info("Conexión a API de BMG establecida.")
    except Exception as e:
        asunto = "Error Crítico en Script 02: Conexión a API de BMG fallida"
        cuerpo = f"El Script 02 no pudo establecer conexión con la API de BMG. Revise la configuración.\n\nError:\n{str(e)}"
        enviar_email(asunto, cuerpo)
        return

    # 3. Conectar a Odoo (una vez para todas las operaciones)
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        asunto = "Error Crítico en Script 02: Conexión a Odoo fallida"
        cuerpo = "El Script 02 no pudo establecer conexión con Odoo. Revise la configuración."
        enviar_email(asunto, cuerpo)
        return

    # 4. Iterar, consultar y actualizar
    for code in pedidos_a_verificar:
        _logger.info(f"  - Verificando estado para el pedido: {code}")
        
        # Obtener estados actuales y odoo_sale_order_id de la DB local para este order_code
        current_trabajos = {}
        sale_order_id = None
        opportunity_id = None # Nuevo: para almacenar el ID de la oportunidad
        project_task_id = None # Nuevo: para almacenar el ID de la tarea de proyecto
        try:
            conn_read = db_conn.conectar_db()
            if conn_read:
                cursor_read = conn_read.cursor()
                cursor_read.execute("SELECT line_number, line_status, line_status_id, odoo_sale_order_id, odoo_sale_order_line_id, odoo_opportunity_id, odoo_project_task_id, title, order_type FROM trabajos WHERE order_code = ?", (code,))
                for row in cursor_read.fetchall():
                    current_trabajos[int(row['line_number'])] = {
                        'line_status': row['line_status'],
                        'line_status_id': row['line_status_id'],
                        'odoo_sale_order_id': row['odoo_sale_order_id'],
                        'odoo_sale_order_line_id': row['odoo_sale_order_line_id'],
                        'odoo_opportunity_id': row['odoo_opportunity_id'],
                        'odoo_project_task_id': row['odoo_project_task_id'],
                        'title': row['title'],
                        'order_type': row['order_type']
                    }
                    if row['odoo_sale_order_id']:
                        sale_order_id = row['odoo_sale_order_id'] # Asumimos que todas las líneas del mismo pedido tienen el mismo SO ID
                    if row['odoo_opportunity_id']:
                        opportunity_id = row['odoo_opportunity_id'] # Asumimos que todas las líneas del mismo pedido tienen el mismo Opportunity ID
                    if row['odoo_project_task_id']:
                        project_task_id = row['odoo_project_task_id'] # Asumimos que todas las líneas del mismo pedido tienen el mismo Project Task ID
                conn_read.close()
        except Exception as e:
            mensaje_error = f"Error al leer estados actuales de la DB para el pedido {code}: {e}"
            _logger.error(mensaje_error)
            asunto = f"Error Script 02: Lectura de estados actuales de DB fallida para pedido {code}"
            enviar_email(asunto, mensaje_error)
            continue # No podemos procesar sin los estados actuales

        if not sale_order_id:
            print(f"    -> Pedido {code} no tiene odoo_sale_order_id. No se publicará en Chatter.")
            # No enviamos email, ya que es un estado esperado si el Script 03 aún no se ejecutó.

        updates_to_perform = []
        changed_lines_for_chatter = []
        
        try:
            resultado_detalle = cliente_wsdl.service.BMBillingByOrder(
                OrderCode=code, 
                FacilityUserId=mapeos.FACILITY_USER_ID, 
                Password=mapeos.PASSWORD
            )
            
            if resultado_detalle is None: 
                print(f"    -> No se obtuvo resultado de BMG para {code}.")
                continue
            order_element = resultado_detalle.find('Order')
            if order_element is None: 
                print(f"    -> No se encontró elemento 'Order' en el resultado de BMG para {code}.")
                continue

            lineas = order_element.findall('Orderline')
            if not lineas: 
                print(f"    -> No se encontraron líneas en el resultado de BMG para {code}.")
                continue

            for linea_element in lineas:
                line_number_elem = linea_element.find('LineNumber')
                new_status_elem = linea_element.find('LineStatus')
                new_status_id_elem = linea_element.find('LineStatusId')

                if line_number_elem is not None and new_status_elem is not None and new_status_id_elem is not None:
                    line_number = int(line_number_elem.text)
                    new_status = new_status_elem.text
                    new_status_id = int(new_status_id_elem.text)
                    
                    # Obtener datos actuales de la línea desde la DB local
                    current_line_data = current_trabajos.get(line_number)
                    if not current_line_data:
                        _logger.warning(f"Línea {line_number} del pedido {code} no encontrada en la DB local. Saltando.")
                        continue

                    old_status = current_line_data['line_status']
                    old_status_id = current_line_data['line_status_id']
                    odoo_sale_order_id = current_line_data['odoo_sale_order_id']
                    
                    # --- DEBUG PRINT ---
                    if code == 'PED00618661':
                        print(f"DEBUG_STATUS: Pedido {code}-{line_number}: Old ID={old_status_id}, New ID={new_status_id}")
                    # --- END DEBUG PRINT ---
                    odoo_opportunity_id = current_line_data['odoo_opportunity_id']
                    odoo_project_task_id = current_line_data['odoo_project_task_id']
                    order_type_bmg = current_line_data['order_type'] # BMG order type (e.g., 'POD', 'eDistrib. 1 a 1')


                    # Detectar cambio de estado
                    if new_status_id != old_status_id:
                        _logger.info(f"  -> CAMBIO DE ESTADO detectado para {code}-{line_number}: De '{old_status}' ({old_status_id}) a '{new_status}' ({new_status_id})")
                        
                        changed_lines_for_chatter.append({
                            'line_number': line_number,
                            'title': current_line_data['title'],
                            'old_status': old_status,
                            'new_status': new_status
                        })

                        # --- Lógica de acciones en Odoo y Push a BMG ---
                        if odoo_api: # Solo si tenemos conexión a Odoo
                            # BMG Status: PRESUPUESTO ENVIADO (ID 2)
                            if new_status_id == bmg_estados_mapeo.get_bmg_status_id("PRESUPUESTO ENVIADO"):
                                if odoo_opportunity_id:
                                    _update_opportunity_stage(odoo_api, odoo_opportunity_id, mapeos.OPPORTUNITY_STAGE_ESPERANDO_RESPUESTA)
                                    _create_activity(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_CONTACTAR_CLIENTE)
                                else:
                                    _logger.warning(f"Pedido {code}-{line_number} en PRESUPUESTO ENVIADO pero sin odoo_opportunity_id para actualizar.")

                            # BMG Status: PENDIENTE DE ORIGINAL (ID 4)
                            elif new_status_id == bmg_estados_mapeo.get_bmg_status_id("PENDIENTE DE ORIGINAL"):
                                if odoo_opportunity_id:
                                    _update_opportunity_stage(odoo_api, odoo_opportunity_id, mapeos.OPPORTUNITY_STAGE_GANADO_SIN_OT)
                                    _mark_activity_done(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_CONTACTAR_CLIENTE) # Marcar previa
                                    _create_activity(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_RECLAMAR_ARCHIVOS)
                                
                                # Si ya existe una tarea de validación, la movemos a la etapa de conseguir archivos
                                if odoo_project_task_id:
                                    _move_project_task_stage(odoo_api, odoo_project_task_id, "Conseguir Archivos o datos")
                                else:
                                    # Si no hay tarea, es normal, puede que el pedido de venta aún no se haya confirmado
                                    _logger.info(f"Pedido {code}-{line_number} en PENDIENTE DE ORIGINAL. No se mueve ninguna tarea porque aún no existe.")
                                    
                            # BMG Status: ARCHIVOS RECIBIDOS WEB (ID 5)
                            elif new_status_id == bmg_estados_mapeo.get_bmg_status_id("ARCHIVOS RECIBIDOS WEB"):
                                _logger.info(f"  -> BMG Status ID 5 (ARCHIVOS RECIBIDOS WEB) detectado para {code}-{line_number}.")
                                if odoo_opportunity_id:
                                    _update_opportunity_stage(odoo_api, odoo_opportunity_id, mapeos.OPPORTUNITY_STAGE_GANADO_CON_OT)
                                    _mark_activity_done(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_RECLAMAR_ARCHIVOS)
                                
                                # Mover la tarea a "Para Validar" y notificar a BMG
                                if mapeos.PRODUCCION_ACTIVADA:
                                    if odoo_project_task_id:
                                        _move_project_task_stage(odoo_api, odoo_project_task_id, mapeos.TASK_STAGE_PARA_VALIDAR)
                                        _create_bmg_notification(
                                            odoo_api,
                                            code,
                                            line_number,
                                            bmg_estados_mapeo.get_bmg_status_id("EN VALIDACIÓN"),
                                            odoo_project_task_id
                                        )
                                    else:
                                        _logger.warning(f"Pedido {code}-{line_number} en ARCHIVOS RECIBIDOS WEB pero sin odoo_project_task_id para mover y notificar.")
                                

                            # BMG Status: MUESTRA RECHAZADA (ID 15)
                            elif new_status_id == bmg_estados_mapeo.get_bmg_status_id("MUESTRA RECHAZADA"):
                                if mapeos.PRODUCCION_ACTIVADA:
                                    if odoo_project_task_id:
                                        _move_project_task_stage(odoo_api, odoo_project_task_id, "Conseguir Archivos o datos")
                                        # Empujar estado "PENDIENTE DE ORIGINAL" a BMG
                                        _create_bmg_notification(
                                            odoo_api,
                                            code,
                                            line_number,
                                            bmg_estados_mapeo.get_bmg_status_id("PENDIENTE DE ORIGINAL")
                                            # No pasar el project_task_id para evitar bug en Odoo
                                        )
                                    else:
                                        _logger.warning(f"Pedido {code}-{line_number} en MUESTRA RECHAZADA pero sin odoo_project_task_id para mover y notificar.")

                            # BMG Status: MUESTRA APROBADA (ID 14)
                            elif new_status_id == bmg_estados_mapeo.get_bmg_status_id("MUESTRA APROBADA"):
                                if mapeos.PRODUCCION_ACTIVADA:
                                    if odoo_project_task_id:
                                        _move_project_task_stage(odoo_api, odoo_project_task_id, "Planificar producción")
                                        _create_bmg_notification(
                                            odoo_api, code, line_number,
                                            bmg_estados_mapeo.get_bmg_status_id("IMPOSICIÓN PENDIENTE")
                                        )
                                    else:
                                        _logger.warning(f"Pedido {code}-{line_number} en MUESTRA APROBADA pero sin odoo_project_task_id para mover a 'Planificar Producción'.")

                            # BMG Status: ANULADO (IDs 38 para POD, 234 para eDist)
                            elif new_status_id in (bmg_estados_mapeo.get_bmg_status_id("ANULADO"), 234):
                                if odoo_sale_order_id:
                                    try:
                                        so = odoo_api.env['sale.order'].browse(odoo_sale_order_id)
                                        if so and so.state not in ('done', 'cancel'):
                                            so.action_cancel()
                                            _logger.info(f"✅ Pedido de Venta {so.name} (ID: {odoo_sale_order_id}) cancelado en Odoo.")
                                        elif so:
                                            _logger.info(f"Pedido de Venta {so.name} (ID: {odoo_sale_order_id}) ya estaba en estado '{so.state}'. No se requiere acción.")
                                    except Exception as e:
                                        _logger.error(f"❌ Error al intentar cancelar el Pedido de Venta ID {odoo_sale_order_id} en Odoo: {e}")
                                else:
                                    _logger.warning(f"Línea {code}-{line_number} anulada en BMG, pero no se encontró Pedido de Venta en Odoo para cancelar.")
                        else:
                            _logger.warning(f"No se realizaron acciones en Odoo para {code}-{line_number} porque la conexión a Odoo no está activa.")
                        
                    updates_to_perform.append((
                        new_status,
                        new_status_id, # Usar el ID numérico
                        datetime.now().isoformat(),
                        code,
                        line_number
                    ))

            # Actualizar la DB en una transacción
            if updates_to_perform:
                conn_update = db_conn.conectar_db()
                if not conn_update: 
                    asunto = f"Error Script 02: Conexión a DB local fallida para actualizar pedido {code}"
                    cuerpo = f"El Script 02 no pudo establecer conexión con la base de datos local para actualizar el pedido {code}."
                    enviar_email(asunto, cuerpo)
                    continue
                
                cursor_update = conn_update.cursor()
                cursor_update.executemany("""
                    UPDATE trabajos 
                    SET line_status = ?, line_status_id = ?, fecha_actualizacion = ?
                    WHERE order_code = ? AND line_number = ?
                """, updates_to_perform)
                conn_update.commit()
                conn_update.close()
                print(f"    -> Estado actualizado para {len(updates_to_perform)} líneas del pedido {code}.")

                # Publicar en Chatter si hubo cambios y hay SO ID
                if changed_lines_for_chatter: # Check if any changes were detected
                    if sale_order_id: # Only attempt Chatter if SO ID is available
                        print(f"    -> DEBUG: Entrando al bloque 'if odoo_api:' para SO ID: {sale_order_id}") # DEBUG PRINT
                        try:
                            message_body = f"**Cambio de estado BMG para pedido {code}:**\n"
                            for change in changed_lines_for_chatter:
                                message_body += f"- Línea {change['line_number']} ({change['title']}): De '{change['old_status']}' a '{change['new_status']}'\n"
                            
                            # Añadir el estado actual de TODAS las líneas del pedido
                            message_body += "\n**Estados actuales de todas las líneas del pedido:**\n"
                            
                            # Crear un diccionario para buscar fácilmente los nuevos estados
                            new_statuses = {change['line_number']: change['new_status'] for change in changed_lines_for_chatter}
                            
                            for ln, data in current_trabajos.items():
                                # Usar el nuevo estado si existe para esta línea, si no, usar el estado antiguo
                                final_status = new_statuses.get(ln, data['line_status'])
                                message_body += f"- Línea {ln} ({data['title']}): {final_status}\n"

                            print(f"    -> DEBUG: Intentando browse y message_post para SO ID: {sale_order_id}") # DEBUG PRINT
                            so_record = odoo_api.env['sale.order'].browse(sale_order_id)
                            so_record.message_post(body=message_body, message_type='comment', subtype_xmlid='mail.mt_note')
                            print(f"    -> ✅ Mensaje de Chatter publicado para SO ID: {sale_order_id} con los cambios detectados.")
                        except Exception as chat_e:
                            error_chatter = f"Error al construir mensaje, obtener registro o publicar en Chatter para SO ID {sale_order_id}: {chat_e}"
                            print(f"    -> ❌ {error_chatter}")
                            asunto_chatter = f"Error Script 02: Fallo al construir mensaje, obtener registro o publicar en Chatter para SO ID {sale_order_id}"
                            cuerpo_chatter = f"El Script 02 intentó construir el mensaje, obtener el registro o publicar un mensaje en el Chatter del Pedido de Venta {sale_order_id} pero falló.\n\nError:\n{error_chatter}\n\nMensaje que se intentó publicar (parcial si el error fue en la construcción):\n{message_body if 'message_body' in locals() else 'No se pudo construir el mensaje.'}"
                            enviar_email(asunto_chatter, cuerpo_chatter)
                    else: # Changes detected but no SO ID
                        print(f"    -> ✅ Se detectaron cambios de estado para el pedido {code}, pero no se publicó en Chatter (SO ID no disponible).")
                else: # No changes detected
                    print(f"    -> ℹ️ No se detectaron cambios de estado para el pedido {code}.")
            else: # If no updates_to_perform (e.g., no lines from BMG API)
                print(f"    -> ℹ️ No se recibieron actualizaciones de estado de BMG para el pedido {code} o no hay líneas válidas.")

        except Exception as e:
            mensaje_error = f"Error INESPERADO procesando la actualización de estado para el pedido {code}: {e}"
            asunto = f"Error INESPERADO en Script 02 para pedido {code}"
            enviar_email(asunto, mensaje_error)
            if sale_order_id:
                try:
                    if not odoo_api: # Conectar a Odoo si es necesario
                        odoo_api = odoo_conn.conectar_odoo()
                        if not odoo_api:
                            asunto = "Error Crítico en Script 02: Conexión a Odoo fallida para Chatter"
                            cuerpo = "El Script 02 no pudo establecer conexión con Odoo para publicar en Chatter."
                            enviar_email(asunto, cuerpo)
                            # No podemos publicar en Chatter, pero el proceso continúa
                            # No hay return aquí, para que el script siga procesando otros pedidos
                    
                    if odoo_api: # Solo intentar publicar si la conexión a Odoo es exitosa
                        so_record = odoo_api.env['sale.order'].browse(sale_order_id)
                        so_record.message_post(body=mensaje_error, message_type='comment', subtype_xmlid='mail.mt_note')
                except Exception as chat_e:
                    print(f"    -> ❌ Error al publicar en Chatter para SO ID {sale_order_id}: {chat_e}")

    print("--- Script 2 Finalizado ---")

if __name__ == "__main__":
    run()
