
from common import odoo_conn

def check_picking_data(picking_name):
    print(f"--- Verificando datos del Picking: {picking_name} ---")
    try:
        odoo = odoo_conn.conectar_odoo()
        if odoo:
            picking = odoo.env['stock.picking'].search_read([('name', '=', picking_name)], 
                ['x_is_meli_delivery', 'x_meli_label_fetched', 'x_meli_shipment_id', 'state'])
            if picking:
                print("Datos encontrados:")
                for key, value in picking[0].items():
                    print(f"  - {key}: {value}")
            else:
                print("No se encontró el picking.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_picking_data('WH/OUT/18715')
