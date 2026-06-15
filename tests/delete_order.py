import sqlite3
import os
from common import db_conn, mapeos

def delete_order_from_db(order_code):
    conn = db_conn.conectar_db()
    if not conn:
        print("Error: No se pudo conectar a la base de datos.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trabajos WHERE order_code = ?", (order_code,))
        conn.commit()
        print(f"Pedido '{order_code}' eliminado de la base de datos.")
    except Exception as e:
        print(f"Error al eliminar el pedido '{order_code}': {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Añadir el directorio padre al sys.path para encontrar 'common'
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Ensure mapeos_local is loaded if present
    try:
        from common import mapeos_local
        for key in dir(mapeos_local):
            if not key.startswith('__'):
                globals()[key] = getattr(mapeos_local, key)
        print("... Configuración local (mapeos_local.py) cargada para el script de eliminación.")
    except ImportError:
        print("... Usando configuración de servidor (mapeos.py) para el script de eliminación.")

    delete_order_from_db('PED00606208')
