# -*- coding: utf-8 -*-
import logging
from common import odoo_conn, meli_api

_logger = logging.getLogger(__name__)

def sincronizar_estados():
    print("\n--- [Sincronizando Estados de Envío desde Mercado Libre] ---")
    
    odoo = odoo_conn.conectar_odoo()
    if not odoo:
        print("❌ No se pudo conectar a Odoo.")
        return

    # 1. Buscar Pickings de ML que tengan la etiqueta descargada
    # Solo procesamos si el operario ya bajó la etiqueta (x_meli_label_fetched)
    dominio = [
        ('x_is_meli_delivery', '=', True),
        ('x_meli_label_fetched', '=', True),
        ('x_meli_shipment_id', '!=', False),
        ('state', 'not in', ['done', 'cancel'])
    ]
    
    picking_ids = odoo.env['stock.picking'].search(dominio)
    if not picking_ids:
        print("ℹ️ No hay pickings de Mercado Libre pendientes de actualización.")
        return

    print(f"🔍 Procesando {len(picking_ids)} pickings pendientes...")

    for picking in odoo.env['stock.picking'].browse(picking_ids):
        ship_id = picking.x_meli_shipment_id
        estado_odoo_actual = picking.state
        
        # Llamar a la función del módulo de Odoo para actualizar
        # Esta función ya consulta a ML y escribe los campos x_meli_shipment_status y x_meli_tracking_number
        try:
            picking.action_meli_update_status()
            
            # Recargar datos después de la actualización de la API
            status_meli = picking.x_meli_shipment_status
            
            # LÓGICA DE CAMBIO DE ESTADO EN ODOO
            
            # A. Si en ML está 'shipped' y en Odoo estaba 'assigned' -> Pasamos a 'enviado'
            if status_meli == 'shipped' and estado_odoo_actual == 'assigned':
                print(f"  🚚 Picking {picking.name}: ML Shipped -> Odoo ENVIADO")
                picking.write({'state': 'enviado'})
                picking.message_post(body="Sistema: Envío detectado en tránsito. Estado Odoo cambiado a 'Enviado'.")

            # B. Si en ML está 'delivered' y en Odoo estaba 'enviado' o 'assigned' -> Pasamos a 'done'
            elif status_meli == 'delivered' and estado_odoo_actual in ['assigned', 'enviado']:
                print(f"  🏁 Picking {picking.name}: ML Delivered -> Odoo HECHO")
                # En Odoo, para pasar a 'done' generalmente se usa button_validate si queremos procesar stock,
                # pero como es una actualización de estado logístico, forzamos el estado o usamos el validador con contexto.
                picking.write({'state': 'done'})
                picking.message_post(body="Sistema: Entrega confirmada por Mercado Libre. Estado Odoo cambiado a 'Hecho'.")

            # C. Si en ML está 'cancelled' -> Cancelamos en Odoo
            elif status_meli == 'cancelled' and estado_odoo_actual != 'cancel':
                print(f"  ❌ Picking {picking.name}: ML Cancelled -> Odoo CANCELADO")
                picking.action_cancel()
                picking.message_post(body="Sistema: Venta cancelada en Mercado Libre. Albarán cancelado automáticamente.")

        except Exception as e:
            print(f"  ⚠️ Error procesando picking {picking.name}: {e}")

    print("--- Sincronización de estados finalizada ---")

def run():
    sincronizar_estados()

if __name__ == "__main__":
    run()
