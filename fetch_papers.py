import odoorpc

URL = 'testkrl.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_stage'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '77436602dbb10c3959d3cf28e12e0cf4d253f667'

ta_codes = [
    "TACAP250", "TACAR240", "TACAR300", "TACHA180", "TACONS280", "TADUCAR", "TAEAR200", "TAESM250",
    "TAESM280", "TAESM320", "TAILB115", "TAILB150", "TAILB170", "TAILB230", "TAILB300", "TAILM115",
    "TAILM150", "TAILM170", "TAILM230", "TAILM250", "TAILU200", "TAILU250", "TAILU270", "TAILU350",
    "TAMOD260", "TAOBR180", "TAOBR240", "TAORO300", "TAREC240", "TAREC300", "TAREV270", "TARLT250",
    "TASBS220", "TASBS250", "TASBS270", "TASBS280", "TATEX012", "TATEX014", "TATINCAM", "TATINCEY",
    "TAVER300B", "TAVER300C", "TAVER300N"
]

def fetch_names():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        # Primero buscar por attribute.value (nombres de valores de atributos)
        vals = odoo.execute('product.attribute.value', 'search_read', 
                               [], ['name'])
        
        print("Attribute values:")
        for v in vals:
            if v['name'] in ta_codes or 'TA' in v['name']:
                print(f"{v['id']}: {v['name']}")
                
        # Buscar en product.template
        print("\nTemplates:")
        tmps = odoo.execute('product.template', 'search_read', 
                               [('default_code', 'in', ta_codes)], ['default_code', 'name'])
        for t in tmps:
            print(f"{t['default_code']}: {t['name']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_names()
