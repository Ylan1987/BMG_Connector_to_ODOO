import odoorpc

URL = 'prod17.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_prod'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'

def fix_multiple_wcs():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        # Pares de (ID Viejo, ID Nuevo)
        pairs = [
            (80, 110)
        ]
        
        for bad_id, good_id in pairs:
            print(f"\n{'='*40}")
            print(f"PROCESANDO MIGRACIÓN DE MÁQUINA {bad_id} -> {good_id}")
            print(f"{'='*40}")
            
            # 1. Mover el External ID
            ext_ids = odoo.execute('ir.model.data', 'search', [('res_id', '=', bad_id), ('model', '=', 'mrp.workcenter')])
            if ext_ids:
                odoo.execute('ir.model.data', 'write', ext_ids, {'res_id': good_id})
                print(f"[OK] {len(ext_ids)} External ID(s) reasignados al ID {good_id}.")
            else:
                print(f"[INFO] La máquina {bad_id} no tenía un External ID asociado.")
                
            # 2. Mover Órdenes de Trabajo Activas
            wos = odoo.execute('mrp.workorder', 'search', [('workcenter_id', '=', bad_id)])
            if wos:
                odoo.execute('mrp.workorder', 'write', wos, {'workcenter_id': good_id})
                print(f"[OK] Se movieron {len(wos)} órdenes de taller activas a la máquina {good_id}.")
            else:
                print(f"[INFO] No había órdenes activas en la máquina {bad_id}.")
                
            # 3. Mover Listas de Materiales (Rutas)
            routings = odoo.execute('mrp.routing.workcenter', 'search', [('workcenter_id', '=', bad_id)])
            if routings:
                odoo.execute('mrp.routing.workcenter', 'write', routings, {'workcenter_id': good_id})
                print(f"[OK] Se movieron {len(routings)} operaciones de Listas de Materiales a la máquina {good_id}.")
            else:
                print(f"[INFO] No había Listas de Materiales usando la máquina {bad_id}.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_multiple_wcs()
