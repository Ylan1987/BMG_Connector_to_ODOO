
import json
import os
from common import odoo_conn, meli_api

def force_sync():
    print("--- [Sincronización Forzada de Token ML a Odoo] ---")
    
    # 1. Cargar token local
    tokens = meli_api._cargar_tokens()
    if not tokens:
        print("❌ No se encontraron tokens locales en meli_tokens.json")
        return
    
    access_token = tokens.get('access_token')
    print(f"Token local recuperado (primeros 10 caracteres): {access_token[:10]}...")

    # 2. Conectar a Odoo
    odoo = odoo_conn.conectar_odoo()
    if not odoo:
        print("❌ No se pudo conectar a Odoo.")
        return

    # 3. Sincronizar usando el método manual (search + write/create)
    try:
        param_obj = odoo.env['ir.config_parameter'].sudo()
        param_key = 'nesta_meli_shipping.meli_access_token'
        
        print(f"Buscando parámetro '{param_key}' en Odoo...")
        param_ids = param_obj.search([('key', '=', param_key)])
        
        if param_ids:
            print(f"Actualizando registro existente (ID: {param_ids[0]})...")
            param_obj.browse(param_ids[0]).write({'value': access_token})
        else:
            print("Creando nuevo registro de parámetro...")
            param_obj.create({'key': param_key, 'value': access_token})
            
        print("✅ ¡Token sincronizado con éxito!")
        
        # 4. Verificación final
        confirm_val = param_obj.get_param(param_key)
        if confirm_val == access_token:
            print("🚀 Verificación exitosa: El valor en Odoo coincide con el local.")
        else:
            print("⚠️ Advertencia: El valor guardado en Odoo parece ser diferente.")

    except Exception as e:
        print(f"🔥 Error durante la sincronización: {e}")

if __name__ == "__main__":
    force_sync()
