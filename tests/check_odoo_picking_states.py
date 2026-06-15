
from common import odoo_conn

def get_picking_states():
    print("--- Obteniendo estados de Stock Picking de Odoo ---")
    try:
        odoo_api = odoo_conn.conectar_odoo()
        if odoo_api:
            # Obtener la definición del campo 'state'
            picking_fields = odoo_api.env['stock.picking'].fields_get(['state'])
            if 'state' in picking_fields:
                selection = picking_fields['state'].get('selection', [])
                print("Estados (state) encontrados en Odoo:")
                for code, label in selection:
                    print(f"  - {code}: {label}")
            else:
                print("No se pudo encontrar el campo 'state' en stock.picking")
        else:
            print("No se pudo conectar con Odoo")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_picking_states()
