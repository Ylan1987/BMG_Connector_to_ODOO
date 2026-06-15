
import sqlite3
import json

def get_order_data(order_code):
    print(f"--- Datos del pedido {order_code} en la DB local ---")
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trabajos WHERE order_code = ?", (order_code,))
    rows = cursor.fetchall()
    
    if not rows:
        print("No se encontró el pedido en la DB.")
    else:
        for row in rows:
            print(f"Línea: {row['line_number']}")
            print(f"  - Canal: {row['channel']}")
            print(f"  - Empresa (en JSON): {json.loads(row['datos_envio_json'])[0].get('Empresa', 'N/A')}")
            print(f"  - JSON Envío: {row['datos_envio_json']}")
    
    conn.close()

if __name__ == "__main__":
    get_order_data('PED00651640')
