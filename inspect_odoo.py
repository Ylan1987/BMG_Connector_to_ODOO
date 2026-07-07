import sys
import os
sys.path.append(r'C:\Users\ylana\Downloads\BMG\V2.0')
from common import odoo_conn
import json

def inspect():
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        print("Failed to connect")
        return
        
    so_ids = odoo_api.env['sale.order'].search([('name', '=', 'P80157')])
    if not so_ids:
        print("SO not found")
        return
    so = odoo_api.env['sale.order'].browse(so_ids[0])
    
    group_id = getattr(so.procurement_group_id, 'id', None) if hasattr(so, 'procurement_group_id') else getattr(so.procurement_group_id, 'id', None)
    
    print(f"SO: {so.name}, state: {so.state}")
    
    print("\nSO Lines:")
    for line in so.order_line:
        print(f" - Line ID: {line.id}, Product: {line.product_id.name}, Qty: {line.product_uom_qty}, Delivered: {line.qty_delivered}")
        
    print("\nPickings linked to SO (so.picking_ids):")
    for picking in so.picking_ids:
        bmg = getattr(picking, 'x_is_bmg_picking', 'N/A')
        print(f" - {picking.name}, State: {picking.state}, is_bmg: {bmg}")

    print("\nSpecific Pickings details:")
    pickings = odoo_api.env['stock.picking'].search([('name', 'in', ['WH/OUT/20428', 'WH/OUT/20429'])])
    for pid in pickings:
        p = odoo_api.env['stock.picking'].browse(pid)
        print(f"\nPicking: {p.name}, State: {p.state}, Sale ID: {p.sale_id.id if p.sale_id else None}")
        for move in getattr(p, 'move_lines', p.move_ids_without_package):
            print(f"   -> Move ID: {move.id}, Product: {move.product_id.name}, Qty: {move.product_uom_qty}, Sale Line ID: {move.sale_line_id.id if move.sale_line_id else None}")

if __name__ == '__main__':
    inspect()
