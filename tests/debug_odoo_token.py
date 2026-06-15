
from common import odoo_conn

def debug_set_param():
    print("--- DEBUG: Probando set_param en Odoo ---")
    try:
        odoo = odoo_conn.conectar_odoo()
        if odoo:
            param_name = 'nesta_meli_shipping.meli_access_token'
            param_value = 'TEST_TOKEN_123'
            
            print(f"Intentando setear {param_name}...")
            # Probando con sudo() y set_param
            odoo.env['ir.config_parameter'].sudo().set_param(param_name, param_value)
            print("✅ set_param ejecutado sin error (aparentemente).")
            
            # Verificar si se guardó
            val = odoo.env['ir.config_parameter'].sudo().get_param(param_name)
            print(f"Valor recuperado: {val}")
            
        else:
            print("No se pudo conectar a Odoo.")
    except Exception as e:
        print(f"🔥 ERROR DETECTADO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_set_param()
