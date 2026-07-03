import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import db_conn

def descongelar_crudos():
    conn = db_conn.conectar_db()
    if not conn:
        print("Error de conexión a la base de datos.")
        return
        
    cursor = conn.cursor()
    
    # 1. Quitar el JSON falso "[]" de pickings a los pedidos que estaban crudos
    cursor.execute("UPDATE trabajos SET odoo_pickings_data_json = NULL WHERE odoo_pickings_data_json = '[]'")
    pickings_revertidos = cursor.rowcount
    
    # 2. Devolver a estado 'PENDIENTE' a los pedidos que NO tienen pickings válidos (los crudos)
    cursor.execute("UPDATE trabajos SET estado_fabricacion = 'PENDIENTE' WHERE odoo_pickings_data_json IS NULL")
    of_revertidas = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print("EXITO. Se han descongelado los pedidos en curso (crudos):")
    print(f"  - {pickings_revertidos} pedidos recuperaron su estado NULL en pickings (Script 4 ya los puede procesar).")
    print(f"  - {of_revertidas} pedidos recuperaron su estado 'PENDIENTE' de fabricacion (Script 5 ya los puede procesar).")
    print("Los pedidos viejos que ya estaban confirmados (con pickings reales) se mantuvieron frizados correctamente.")

if __name__ == '__main__':
    descongelar_crudos()
