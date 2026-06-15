import common.odoo_conn as odoo_conn
import common.mapeos as mapeos

def check_analytic_accounts():
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        print("Error conectando a Odoo")
        return

    print(f"Buscando cuentas analíticas en {mapeos.ODOO_DB}...")
    accounts = odoo_api.env['account.analytic.account'].search_read([], ['id', 'name'])
    for acc in accounts:
        print(f"- ID {acc['id']}: {acc['name']}")

if __name__ == "__main__":
    check_analytic_accounts()
