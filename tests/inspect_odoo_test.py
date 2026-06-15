from common import odoo_conn
import json

def inspect_records():
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        print("Fallo conexión Odoo")
        return

    # ID del contacto que devolvió el Script 04
    partner_id = 137063
    p = odoo_api.env['res.partner'].browse(partner_id)
    print(f"--- CONTACTO ID {partner_id} ---")
    print(f"Nombre: {p.name}")
    print(f"Parent: {p.parent_id.name if p.parent_id else 'Suelto'}")
    print(f"Type: {p.type}")
    print(f"Display Name: {p.display_name}")

    # ID de la SO creada
    so_id = 26483
    so = odoo_api.env['sale.order'].browse(so_id)
    print(f"\n--- SALE ORDER ID {so_id} ---")
    print(f"Partner: {so.partner_id.name}")
    print(f"Partner Shipping: {so.partner_shipping_id.name} (ID: {so.partner_shipping_id.id})")

    # ID del Picking creado
    picking_id = 18712
    pick = odoo_api.env['stock.picking'].browse(picking_id)
    print(f"\n--- PICKING ID {picking_id} ---")
    print(f"Partner en Picking: {pick.partner_id.name} (ID: {pick.partner_id.id})")
    print(f"Partner Display Name: {pick.partner_id.display_name}")

if __name__ == "__main__":
    inspect_records()
