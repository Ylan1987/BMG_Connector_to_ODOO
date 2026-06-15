import sqlite3

def check_order(order_code):
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trabajos WHERE order_code = ?", (order_code,))
    rows = cursor.fetchall()
    if not rows:
        print(f"No se encontró el pedido {order_code}")
        return
    
    for row in rows:
        print(f"--- Line {row['line_number']} ---")
        for key in row.keys():
            print(f"{key}: {row[key]}")
    conn.close()

if __name__ == "__main__":
    check_order('PED00651416')
