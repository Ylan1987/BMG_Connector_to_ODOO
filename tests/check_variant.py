import sqlite3
import os

db_path = 'trabajos.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

order_code = 'PED00650514'
cursor.execute("SELECT order_code, line_number, odoo_product_variant_id FROM trabajos WHERE order_code = ?", (order_code,))
rows = cursor.fetchall()

for row in rows:
    print(f"Variant ID: {row['odoo_product_variant_id']}")

conn.close()
