import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import db_conn

def congelar_viejos():
    conn = db_conn.conectar_db()
    if not conn:
        print("❌ Error de conexión a la base de datos.")
        return
        
    cursor = conn.cursor()
    
    # 1. Simular que ya se les crearon los Pickings (Script 04 los ignora)
    cursor.execute("UPDATE trabajos SET odoo_pickings_data_json = '[]' WHERE odoo_pickings_data_json IS NULL AND odoo_sale_order_id IS NOT NULL")
    pickings_congelados = cursor.rowcount
    
    # 2. Simular que ya se les crearon las Órdenes de Fabricación (Script 05 los ignora)
    cursor.execute("UPDATE trabajos SET estado_fabricacion = 'OF_CREADA' WHERE estado_fabricacion != 'OF_CREADA' OR estado_fabricacion IS NULL")
    of_congeladas = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ ÉXITO. Se han congelado los pedidos viejos para que no generen producción:")
    print(f"  - {pickings_congelados} líneas marcadas para saltar la confirmación (Script 04).")
    print(f"  - {of_congeladas} líneas marcadas para saltar la creación de OFs (Script 05).")
    print("A partir de ahora, solo los pedidos NUEVOS (los que entren hoy) van a pasar por el flujo de producción.")

if __name__ == '__main__':
    congelar_viejos()
