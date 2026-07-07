import odoorpc

URL = 'prod17.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_prod'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'

def fix_workcenters():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        print("Buscando el ID del Workcenter correcto a través de ir.model.data...")
        # Get the real ID from the external ID
        model_data = odoo.execute('ir.model.data', 'search_read', 
                                  [('module', '=', '__export__'), ('name', '=', 'mrp_workcenter_empaquetadora_termocontraible_dibipack_4255')],
                                  ['res_id'])
        if not model_data:
            print("No se encontró el external ID.")
            return
            
        correct_wc_id = model_data[0]['res_id']
        print(f"Correct Workcenter ID: {correct_wc_id}")
        
        # Buscar todas las workorders que NO tengan el correct_wc_id pero se llamen "Empacar" o tengan ese centro
        # Mejor buscar por nombre del workcenter
        print("Buscando workorders con otro centro...")
        wrong_wos = odoo.execute('mrp.workorder', 'search_read', 
                                 [('workcenter_id', '!=', correct_wc_id), ('workcenter_id.name', 'ilike', 'Dibipack')],
                                 ['name', 'workcenter_id'])
        
        if wrong_wos:
            wrong_ids = [wo['id'] for wo in wrong_wos]
            print(f"Se encontraron {len(wrong_ids)} mrp.workorder incorrectos.")
            odoo.execute('mrp.workorder', 'write', wrong_ids, {'workcenter_id': correct_wc_id})
            print("mrp.workorder actualizados!")
        else:
            print("No se encontraron mrp.workorder con centros incorrectos.")
            
        # También arreglemos las operaciones de las listas de materiales (mrp.routing.workcenter)
        wrong_routings = odoo.execute('mrp.routing.workcenter', 'search_read', 
                                      [('workcenter_id', '!=', correct_wc_id), ('workcenter_id.name', 'ilike', 'Dibipack')],
                                      ['name', 'workcenter_id'])
        if wrong_routings:
            wrong_routing_ids = [r['id'] for r in wrong_routings]
            print(f"Se encontraron {len(wrong_routing_ids)} mrp.routing.workcenter incorrectos.")
            odoo.execute('mrp.routing.workcenter', 'write', wrong_routing_ids, {'workcenter_id': correct_wc_id})
            print("mrp.routing.workcenter actualizados!")
        else:
            print("No se encontraron operaciones de lista de materiales con centros incorrectos.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_workcenters()
