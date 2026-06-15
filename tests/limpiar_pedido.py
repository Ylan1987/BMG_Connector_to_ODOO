import sqlite3
from common import mapeos

def limpiar_pedido(order_code):
    db_path = 'trabajos.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Limpiando pedido {order_code} en la DB local...")
    
    # Limpiamos todos los campos que vinculan el pedido con Odoo
    cursor.execute("""
        UPDATE trabajos 
        SET odoo_sale_order_id = NULL,
            odoo_sale_order_line_id = NULL,
            odoo_partner_id = NULL,
            odoo_opportunity_id = NULL,
            odoo_product_variant_id = NULL,
            odoo_pickings_data_json = NULL,
            odoo_project_task_id = NULL,
            estado_odoo = ?
        WHERE order_code = ?
    """, (mapeos.LOCAL_DB_STATUS_LISTO_PARA_SINCRONIZAR, order_code))
    
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    print(f"Hecho. Filas afectadas: {rows_affected}")

if __name__ == "__main__":
    limpiar_pedido('PED00650514')
