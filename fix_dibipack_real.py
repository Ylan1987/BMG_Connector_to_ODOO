import odoorpc

URL = 'prod17.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_prod'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'

def fix_everything():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        BAD_ID = 65
        GOOD_ID = 95
        
        # 1. Mover el External ID al Workcenter correcto (95)
        # Así la próxima vez que los scripts busquen esa máquina, agarren la 95.
        print("1. Reasignando el External ID al Workcenter 95...")
        ext_ids = odoo.execute('ir.model.data', 'search', [('module', '=', '__export__'), ('name', '=', 'mrp_workcenter_empaquetadora_termocontraible_dibipack_4255')])
        if ext_ids:
            odoo.execute('ir.model.data', 'write', ext_ids, {'res_id': GOOD_ID})
            print(f"External ID reasignado al ID {GOOD_ID}.")
            
        # 2. Mover las órdenes de trabajo activas de 65 a 95
        print("\n2. Moviendo Órdenes de Trabajo activas (mrp.workorder)...")
        wos = odoo.execute('mrp.workorder', 'search', [('workcenter_id', '=', BAD_ID)])
        if wos:
            odoo.execute('mrp.workorder', 'write', wos, {'workcenter_id': GOOD_ID})
            print(f"Se movieron {len(wos)} órdenes de taller activas a la máquina 95.")
            
        # 3. Mover las Listas de Materiales (mrp.routing.workcenter) de 65 a 95
        print("\n3. Moviendo Operaciones en Listas de Materiales (mrp.routing.workcenter)...")
        routings = odoo.execute('mrp.routing.workcenter', 'search', [('workcenter_id', '=', BAD_ID)])
        if routings:
            odoo.execute('mrp.routing.workcenter', 'write', routings, {'workcenter_id': GOOD_ID})
            print(f"Se movieron {len(routings)} operaciones de listas de materiales a la máquina 95.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_everything()
