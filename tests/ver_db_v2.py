import sqlite3

def check_db():
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Últimos 5 pedidos en la base de datos:")
    cursor.execute("SELECT order_code, line_number, estado_odoo, odoo_sale_order_id FROM trabajos ORDER BY rowid DESC LIMIT 5")
    for row in cursor.fetchall():
        print(f"Pedido: {row['order_code']} - Línea: {row['line_number']} - Estado Odoo: {row['estado_odoo']} - SO ID: {row['odoo_sale_order_id']}")
    
    conn.close()

if __name__ == "__main__":
    check_db()
