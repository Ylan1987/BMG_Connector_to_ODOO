import sqlite3
import os
from common import mapeos

def reset_order(order_code):
    db_path = mapeos.DB_FILE
    if not os.path.exists(db_path):
        db_path = 'trabajos.db'
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Resetting {order_code} in database...")
    cursor.execute("""
        UPDATE trabajos 
        SET estado_odoo = 'LISTO_PARA_SINCRONIZAR',
            odoo_sale_order_id = NULL,
            odoo_opportunity_id = NULL,
            odoo_product_variant_id = NULL
        WHERE order_code = ?
    """, (order_code,))
    
    conn.commit()
    print(f"Rows affected: {cursor.rowcount}")
    conn.close()

if __name__ == "__main__":
    reset_order("PED00653636")
