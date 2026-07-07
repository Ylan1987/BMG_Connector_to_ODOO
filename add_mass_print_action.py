import odoorpc

URL = 'prod17.odoo.imprentadiagonal.com.uy'
DB = 'odoo17_prod'
USER = 'ylan.archimowicz@imprentadiagonal.com.uy'
PASS = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'

def create_server_action():
    try:
        odoo = odoorpc.ODOO(URL, protocol='jsonrpc+ssl', port=443)
        odoo.login(DB, USER, PASS)
        
        # 1. Crear la etiqueta "Impreso" si no existe
        tag_model = odoo.env['crm.tag'] # En Odoo 17 las etiquetas de ventas suelen estar en crm.tag
        tag_ids = tag_model.search([('name', '=', 'Impreso')])
        if not tag_ids:
            tag_id = tag_model.create({'name': 'Impreso', 'color': 10}) # 10 suele ser verde
            print(f"Etiqueta 'Impreso' creada con ID {tag_id}")
        else:
            tag_id = tag_ids[0]
            print(f"La etiqueta 'Impreso' ya existe con ID {tag_id}")
            
        # 2. Buscar el modelo sale.order
        model_id = odoo.env['ir.model'].search([('model', '=', 'sale.order')])[0]
        
        # 3. Crear la Acción de Servidor
        action_name = "Marcar como Impreso"
        action_env = odoo.env['ir.actions.server']
        
        # Revisar si ya existe
        existing = action_env.search([('name', '=', action_name), ('model_id', '=', model_id)])
        if existing:
            print("La acción de servidor ya existe, actualizando...")
            action = existing[0]
        else:
            code = f"""
for record in records:
    record.write({{'tag_ids': [(4, {tag_id})]}})
"""
            action = action_env.create({
                'name': action_name,
                'model_id': model_id,
                'state': 'code',
                'code': code,
                'binding_model_id': model_id,
                'binding_type': 'action',
            })
            print(f"Acción '{action_name}' creada con éxito. Ahora aparecerá en el menú Acción.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_server_action()
