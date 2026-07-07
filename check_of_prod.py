import odoorpc

URL = 'prod17.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_prod'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'

def check_of():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        # Buscar las ultimas 5 Ordenes de Fabricacion
        of_ids = odoo.execute('mrp.production', 'search', [], 0, 5, 'id desc')
        ofs = odoo.execute('mrp.production', 'read', of_ids, ['name', 'state', 'workorder_ids', 'product_id', 'origin'])
        
        print(f"Encontradas {len(ofs)} OFs recientes en PROD:")
        for of in ofs:
            print(f"\n--- OF: {of['name']} (Estado: {of['state']}) | Origen: {of.get('origin')} | Producto: {of['product_id'][1] if of['product_id'] else 'N/A'} ---")
            
            if of['workorder_ids']:
                wos = odoo.execute('mrp.workorder', 'read', 
                                   of['workorder_ids'], 
                                   ['name', 'state', 'workcenter_id', 'date_start', 'is_user_working'])
                for wo in wos:
                    wc_name = wo['workcenter_id'][1] if wo['workcenter_id'] else 'N/A'
                    print(f"  -> Tarea: {wo['name']} | Centro: {wc_name} | Estado: {wo['state']} | Working: {wo.get('is_user_working')}")
            else:
                print("  -> No tiene workorders (operaciones de taller).")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_of()
