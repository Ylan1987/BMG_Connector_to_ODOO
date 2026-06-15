import sqlite3
import os

db_path = 'trabajos.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

order_code = 'PED00650514'
cursor.execute("SELECT order_code, line_number, estado_odoo, odoo_sale_order_id, printing_facility FROM trabajos WHERE order_code = ?", (order_code,))
rows = cursor.fetchall()

if not rows:
    print(f"No se encontró el pedido {order_code}")
else:
    print(f"{'Order':<15} {'Line':<5} {'Estado Odoo':<20} {'SO ID':<10} {'Prn Facility':<15}")
    print("-" * 65)
    for row in rows:
        print(f"{row['order_code']:<15} {row['line_number']:<5} {str(row['estado_odoo']):<20} {str(row['odoo_sale_order_id']):<10} {str(row['printing_facility']):<15}")

conn.close()
