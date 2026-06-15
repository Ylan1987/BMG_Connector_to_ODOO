import sqlite3
import json

conn = sqlite3.connect('trabajos.db')
cursor = conn.cursor()
query = """
SELECT order_code, line_number, line_status, odoo_pickings_data_json, order_date
FROM trabajos 
WHERE estado_interior_produccion = 'PENDIENTE' OR estado_tapa_produccion = 'PENDIENTE'
ORDER BY order_date DESC
"""
cursor.execute(query)
results = cursor.fetchall()
print(f"{'Order Code':<15} | {'Line':<4} | {'BMG Status':<22} | {'Has Picking?':<12} | {'Picking IDs':<15}")
print("-" * 80)
for row in results:
    order_code, line_number, status, pickings_json, date = row
    has_picking = "SI" if pickings_json and pickings_json != '[]' else "NO"
    
    picking_ids = ""
    if has_picking == "SI":
        try:
            data = json.loads(pickings_json)
            picking_ids = ", ".join([str(p.get('picking_id')) for p in data])
        except:
            picking_ids = "Error JSON"

    print(f"{order_code:<15} | {line_number:<4} | {status if status else 'N/A':<22} | {has_picking:<12} | {picking_ids:<15}")
conn.close()
