
from common import odoo_conn

def check_picking_fields():
    print("--- Verificando campos de stock.picking ---")
    try:
        odoo = odoo_conn.conectar_odoo()
        if odoo:
            fields = odoo.env['stock.picking'].fields_get([])
            print(f"¿Existe 'number_of_packages'?: {'number_of_packages' in fields}")
            print(f"¿Existe 'shipping_weight'?: {'shipping_weight' in fields}")
            
            # Ver qué campos de paquetes o bultos existen
            package_fields = [f for f in fields if 'package' in f or 'bulto' in f]
            print(f"Campos relacionados con paquetes/bultos: {package_fields}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_picking_fields()
