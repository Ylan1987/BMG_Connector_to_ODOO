# -*- coding: utf-8 -*-
"""
Acciones en Odoo (mover tarea de proyecto, actualizar oportunidad, notificar a BMG)
correspondientes a un estado de BMG.

Compartido por:
- script_02_actualizar_estados_bmg.py: lo llama cuando DETECTA un cambio de estado.
- script_04_confirmar_ventas_y_crear_pickings.py: lo llama una vez, al crear la tarea
  de validación, para sincronizarla con el estado BMG ACTUAL del pedido (que puede
  ya estar más adelantado que el estado inicial esperado, ej. archivos ya recibidos
  antes de que el pedido se sincronizara por primera vez).
"""

import logging
from datetime import datetime, timedelta

from common import mapeos
import common.bmg_estados_mapeo as bmg_estados_mapeo

_logger = logging.getLogger(__name__)


def _update_opportunity_stage(odoo_api, opportunity_id, stage_name):
    """Actualiza la etapa de una oportunidad en Odoo."""
    if not opportunity_id:
        _logger.warning("No se puede actualizar la etapa de la oportunidad: opportunity_id es None.")
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
        model_ids = odoo_api.env['ir.model'].search([('model', '=', res_model)], limit=1)
        activity_type_ids = odoo_api.env['mail.activity.type'].search([('name', '=', mapeos.ODOO_ACTIVITY_TYPE_TODO)], limit=1)
        activity_vals = {
            'res_id': res_id,
            'res_model_id': model_ids[0],
            'summary': summary,
            'activity_type_id': activity_type_ids[0],
            'date_deadline': date_deadline if date_deadline else (datetime.now() + timedelta(days=mapeos.ODOO_ACTIVITY_DEADLINE_DAYS)).strftime('%Y-%m-%d'),
        }
        if user_id:
            activity_vals['user_id'] = user_id

        new_activity_id = odoo_api.env['mail.activity'].create(activity_vals)
        _logger.info(f"Actividad '{summary}' creada para {res_model} ID {res_id}. ID Actividad: {new_activity_id}")
        return new_activity_id
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
            ('state', 'in', ['overdue', 'today'])
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
    """Crea un registro en bmg.notification.queue para enviar un estado a BMG."""
    try:
        queue_vals = {
            'order_code': order_code,
            'order_line': order_line_number,
            'bmg_state_id': bmg_state_id,
            'state': 'pending',
        }
        if project_task_id:
            queue_vals['project_task_id'] = project_task_id

        new_queue_record_id = odoo_api.env['bmg.notification.queue'].create(queue_vals)
        _logger.info(f"Registro en bmg.notification.queue creado para Pedido BMG {order_code}-{order_line_number}, Estado BMG: {bmg_state_id}. ID: {new_queue_record_id}")
        return new_queue_record_id
    except Exception as e:
        _logger.error(f"Error al crear registro en bmg.notification.queue para Pedido BMG {order_code}-{order_line_number}, Estado BMG {bmg_state_id}: {e}")
        return None


def _move_project_task_stage(odoo_api, project_task_id, stage_name):
    """Mueve una tarea de proyecto a una etapa específica en Odoo. Es idempotente: si ya está ahí, no hace nada."""
    if not project_task_id:
        _logger.warning("No se puede mover la etapa de la tarea de proyecto: project_task_id es None.")
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
        _logger.info("Archivado de tarea de proyecto OMITIDO (Toggle producción desactivado).")
        return False
    if not project_task_id:
        _logger.warning("No se puede archivar la tarea de proyecto: project_task_id es None.")
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


def aplicar_accion_por_estado_bmg(odoo_api, new_status_id, code, line_number,
                                   odoo_opportunity_id=None, odoo_project_task_id=None, odoo_sale_order_id=None):
    """
    Aplica en Odoo la acción que corresponde al estado BMG `new_status_id` actual
    del pedido `code`-`line_number` (mover tarea de proyecto, actualizar oportunidad,
    notificar a BMG, cancelar pedido de venta, etc.).

    Es idempotente (las funciones de movimiento de etapa no hacen nada si la tarea/
    oportunidad ya está en la etapa correcta), así que se puede llamar tanto ante un
    cambio de estado detectado como para sincronizar el estado actual de un pedido
    recién creado.
    """
    if not odoo_api:
        _logger.warning(f"No se realizaron acciones en Odoo para {code}-{line_number} porque la conexión a Odoo no está activa.")
        return

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
            _mark_activity_done(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_CONTACTAR_CLIENTE)
            _create_activity(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_RECLAMAR_ARCHIVOS)

        if odoo_project_task_id:
            _move_project_task_stage(odoo_api, odoo_project_task_id, "Conseguir Archivos o datos")
        else:
            _logger.info(f"Pedido {code}-{line_number} en PENDIENTE DE ORIGINAL. No se mueve ninguna tarea porque aún no existe.")

    # BMG Status: ARCHIVOS RECIBIDOS WEB (ID 5)
    elif new_status_id == bmg_estados_mapeo.get_bmg_status_id("ARCHIVOS RECIBIDOS WEB"):
        _logger.info(f"  -> BMG Status ID 5 (ARCHIVOS RECIBIDOS WEB) detectado para {code}-{line_number}.")
        if odoo_opportunity_id:
            _update_opportunity_stage(odoo_api, odoo_opportunity_id, mapeos.OPPORTUNITY_STAGE_GANADO_CON_OT)
            _mark_activity_done(odoo_api, odoo_opportunity_id, 'crm.lead', mapeos.ACTIVITY_SUMMARY_RECLAMAR_ARCHIVOS)

        if mapeos.PRODUCCION_ACTIVADA:
            if odoo_project_task_id:
                _move_project_task_stage(odoo_api, odoo_project_task_id, mapeos.TASK_STAGE_PARA_VALIDAR)
                _create_bmg_notification(
                    odoo_api, code, line_number,
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
                _create_bmg_notification(
                    odoo_api, code, line_number,
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
            so = odoo_api.env['sale.order'].browse(odoo_sale_order_id)

            # BUG encontrado el 2026-09-17 con datos reales (P83405/PED00681708):
            # sale.order.action_cancel() nativo, cuando el pedido NO esta en
            # borrador (_show_cancel_wizard() -> True para cualquier state !=
            # 'draft'), no cancela nada - solo devuelve el dict de una ventana
            # emergente para que un humano la complete a mano. Sin
            # disable_cancel_warning en el contexto, la llamada no tira
            # excepcion y este codigo logueaba "cancelado" igual, sin haber
            # cancelado un solo pedido de verdad (confirmado leyendo
            # sale/models/sale_order.py:1010 en el servidor).
            try:
                if so and so.state not in ('done', 'cancel'):
                    so.with_context(disable_cancel_warning=True).action_cancel()
                    # so.state (odoorpc) queda con el valor cacheado de antes
                    # de la llamada - releer directo para confirmar que
                    # realmente quedo en 'cancel', no confiar en la ausencia
                    # de excepcion (ver bug documentado arriba).
                    estado_post = odoo_api.env['sale.order'].read([odoo_sale_order_id], ['state'])[0]['state']
                    if estado_post == 'cancel':
                        _logger.info(f"✅ Pedido de Venta {so.name} (ID: {odoo_sale_order_id}) cancelado en Odoo.")
                    else:
                        _logger.error(f"❌ action_cancel() en Pedido de Venta {so.name} (ID: {odoo_sale_order_id}) no dejo el pedido en 'cancel' (quedo en '{estado_post}').")
                elif so:
                    _logger.info(f"Pedido de Venta {so.name} (ID: {odoo_sale_order_id}) ya estaba en estado '{so.state}'. No se requiere acción.")
            except Exception as e:
                _logger.error(f"❌ Error al intentar cancelar el Pedido de Venta ID {odoo_sale_order_id} en Odoo: {e}")

            # Cancelar tambien las OF de este pedido (interior/tapa/libro/color -
            # mismo criterio de busqueda que usa
            # script_05_crear_ordenes_fabricacion.py para encontrar las OF de
            # un pedido: origin == nombre corto de la SO). Si alguna OF ya
            # tiene trabajo real hecho/en curso y Odoo rechaza cancelarla, se
            # loguea el error puntual y se sigue con el resto - una OF
            # bloqueada no debe frenar a las demas.
            try:
                mrp_production_model = odoo_api.env['mrp.production']
                of_ids = mrp_production_model.search([
                    ('origin', '=', so.name),
                    ('state', 'not in', ('done', 'cancel')),
                ])
                for of_id in of_ids:
                    of_record = mrp_production_model.browse(of_id)
                    try:
                        of_record.action_cancel()
                        _logger.info(f"✅ OF {of_record.name} (ID: {of_id}) cancelada en Odoo (pedido {so.name} anulado).")
                    except Exception as e:
                        _logger.error(f"❌ Error al intentar cancelar la OF {of_record.name} (ID: {of_id}): {e}")
            except Exception as e:
                _logger.error(f"❌ Error al buscar las OF del Pedido de Venta {so.name} para cancelar: {e}")

            # Borrar la imagen de portada: el adjunto 'tapa-miniatura...' de
            # cada linea del pedido (asi la guarda taller_bar_code al
            # generarla), y el campo x_image (+ el de sus workorders) en las
            # OF - mismo campo/alcance que ya sincroniza
            # mrp.production.action_resize_and_sync_to_workorders.
            try:
                if so.order_line:
                    attachment_model = odoo_api.env['ir.attachment']
                    tapa_ids = attachment_model.search([
                        ('res_model', '=', 'sale.order.line'),
                        ('res_id', 'in', so.order_line.ids),
                        ('name', 'ilike', 'tapa-miniatura%'),
                    ])
                    if tapa_ids:
                        attachment_model.browse(tapa_ids).unlink()
                        _logger.info(f"✅ {len(tapa_ids)} adjunto(s) de portada borrados de las líneas del Pedido de Venta {so.name}.")
            except Exception as e:
                _logger.error(f"❌ Error al borrar la imagen de portada del Pedido de Venta {so.name}: {e}")

            try:
                mrp_production_model = odoo_api.env['mrp.production']
                todas_las_of_ids = mrp_production_model.search([('origin', '=', so.name)])
                if todas_las_of_ids:
                    mrp_production_model.browse(todas_las_of_ids).write({'x_image': False})
                    # BUG encontrado el 2026-09-17 (corrida real contra
                    # P83405): a diferencia de Odoo nativo, el .mapped() de
                    # odoorpc sobre un campo relacional no devuelve un
                    # recordset navegable de workorder_ids, tira
                    # "'str' object has no attribute 'write'". Se busca la
                    # mrp.workorder directo por production_id, igual que el
                    # resto de este archivo hace con otras relaciones.
                    wo_model = odoo_api.env['mrp.workorder']
                    wo_ids = wo_model.search([('production_id', 'in', todas_las_of_ids)])
                    if wo_ids:
                        wo_model.browse(wo_ids).write({'x_image': False})
                    _logger.info(f"✅ Imagen de portada limpiada en {len(todas_las_of_ids)} OF y {len(wo_ids)} workorder(s) del Pedido de Venta {so.name}.")
            except Exception as e:
                _logger.error(f"❌ Error al borrar la imagen de portada de las OF del Pedido de Venta {so.name}: {e}")
        else:
            _logger.warning(f"Línea {code}-{line_number} anulada en BMG, pero no se encontró Pedido de Venta en Odoo para cancelar.")
