import sys
sys.path.append(r'C:\Users\ylana\Downloads\BMG\V2.0')
from common import odoo_conn
import json

def get_picking_details():
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        return
    
    pickings = odoo_api.env['stock.picking'].search([('name', 'in', ['WH/OUT/20428', 'WH/OUT/20429'])])
    
    data = {}
    for pid in pickings:
        p = odoo_api.env['stock.picking'].browse(pid)
        moves_info = []
        # Fallback to move_ids_without_package if move_lines is problematic
        moves = getattr(p, 'move_ids_without_package', [])
        if not moves:
             moves = getattr(p, 'move_lines', [])
             
        for move in moves:
            moves_info.append({
                'product': move.product_id.name,
                'variant_id': move.product_id.id,
                'qty': move.product_uom_qty,
                'sale_line_id': move.sale_line_id.id if move.sale_line_id else None
            })
        
        data[p.name] = {
            'state': p.state,
            'sale_id': p.sale_id.id if p.sale_id else None,
            'group_id': p.group_id.id if p.group_id else None,
            'move_count': len(moves_info),
            'moves': moves_info
        }
    
    print(json.dumps(data, indent=2))

if __name__ == '__main__':
    get_picking_details()
