# -*- coding: utf-8 -*-
"""
Script 8: Crear Tarjeta de Proyecto en Odoo

Este script se encarga de crear una tarjeta (tarea) en el módulo de Proyectos de Odoo,
vinculada a un Pedido de Venta y a una línea de Pedido de Venta específica.
"""

import logging
from common import odoo_conn, mapeos

_logger = logging.getLogger(__name__)

def crear_tarjeta_proyecto(odoo_sale_order_id, odoo_sale_order_line_id, task_name, description, project_name=mapeos.PROJECT_NAME_PRE_PRODUCCION):
    if not mapeos.PRODUCCION_ACTIVADA:
        _logger.info("Creación de tarjeta de proyecto OMITIDA (Toggle producción desactivado en mapeos.py).")
        return None
    # --- DEBUG PRINT ---
    _logger.info(f"DEBUG_SCRIPT_08: Recibido odoo_sale_order_line_id='{odoo_sale_order_line_id}' para la tarea '{task_name}'")
    # --- END DEBUG ---
    """
    Crea una tarjeta (tarea) en un proyecto de Odoo.

    Args:
        odoo_sale_order_id (int): ID del Pedido de Venta en Odoo.
        odoo_sale_order_line_id (int): ID de la Línea de Pedido de Venta en Odoo.
        task_name (str): Nombre de la tarea/tarjeta.
        description (str): Descripción de la tarea.
        project_name (str): Nombre del proyecto en Odoo donde se creará la tarea.

    Returns:
        int or None: El ID de la tarea creada en Odoo, o None si falla.
    """
    _logger.info(f"Intentando crear tarjeta de proyecto para SO ID: {odoo_sale_order_id}, SO Line ID: {odoo_sale_order_line_id}")

    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        _logger.error("No se pudo conectar a Odoo para crear la tarjeta de proyecto.")
        return None

    try:
        # 1. Buscar el proyecto
        project_ids = odoo_api.env['project.project'].search([('name', '=', project_name)], limit=1)
        if not project_ids:
            _logger.error(f"No se encontró el proyecto '{project_name}' en Odoo. No se puede crear la tarea.")
            return None
        project_id = project_ids[0]
        
        # Buscar la etapa "Para validar"
        stage_ids = odoo_api.env['project.task.type'].search([('name', '=', mapeos.TASK_STAGE_PARA_VALIDAR), ('project_ids', 'in', [project_id])], limit=1)
        if not stage_ids:
            _logger.error(f"No se encontró la etapa '{mapeos.TASK_STAGE_PARA_VALIDAR}' para el proyecto '{project_name}'.")
            return None
        stage_id = stage_ids[0]

        # 2. Crear la tarea
        task_vals = {
            'name': task_name,
            'project_id': project_id,
            'sale_order_id': odoo_sale_order_id,
            'sale_line_id': odoo_sale_order_line_id,
            'description': description,
            'stage_id': stage_id,
        }
        
        new_task_id = odoo_api.env['project.task'].create(task_vals)
        _logger.info(f"Tarjeta de proyecto '{task_name}' creada con éxito en Odoo. ID: {new_task_id.id}")
        return new_task_id.id

    except Exception as e:
        _logger.error(f"Error al crear la tarjeta de proyecto en Odoo: {e}")
        return None

def run():
    """
    Función de prueba para crear una tarjeta de proyecto.
    Normalmente, esta función sería llamada por Script 02.
    """
    _logger.info("Ejecutando Script 8 en modo de prueba.")
    # Ejemplo de uso (estos IDs deberían venir de la DB local o de Script 02)
    test_so_id = 1 # Reemplazar con un ID de SO real en tu Odoo de prueba
    test_so_line_id = 1 # Reemplazar con un ID de SO Line real
    test_task_name = "Validación de Diseño - PED123-1"
    test_description = "Descripción de la línea de pedido para validación."
    
    crear_tarjeta_proyecto(test_so_id, test_so_line_id, test_task_name, test_description)

if __name__ == "__main__":
    run()
