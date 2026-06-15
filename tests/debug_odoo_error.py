import odoorpc
from common import mapeos

def test_odoo_company():
    try:
        odoo = odoorpc.ODOO(
            mapeos.ODOO_URL,
            protocol='jsonrpc+ssl',
            port=443,
            timeout=120
        )
        odoo.login(
            mapeos.ODOO_DB,
            login=mapeos.ODOO_USUARIO,
            password=mapeos.ODOO_CONTRASENA
        )
        print("✅ Conexión a Odoo exitosa.")
        
        # Intentar leer la compañía actual
        user_data = odoo.env['res.users'].browse(odoo.env.uid)
        company = user_data.company_id
        print(f"Compañía: {company.name} (ID: {company.id})")
        
        # Intentar leer explícitamente el campo que falla
        try:
            val = company.krl_uy_dgi_v25_start_date
            print(f"Valor de krl_uy_dgi_v25_start_date: {val}")
        except Exception as e:
            print(f"❌ Error al leer krl_uy_dgi_v25_start_date: {e}")

    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    test_odoo_company()
