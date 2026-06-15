import sqlite3

def inspect_db():
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- TABLES ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for table in cursor.fetchall():
        print(table['name'])
        
    print("\n--- DATA FOR PED00653636 ---")
    cursor.execute("SELECT order_code, line_number, fecha_actualizacion, order_date, line_status, line_status_id, estado_odoo FROM trabajos WHERE order_code = 'PED00653636'")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))
        
    conn.close()

if __name__ == "__main__":
    inspect_db()
