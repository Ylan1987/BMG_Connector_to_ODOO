import sqlite3
conn = sqlite3.connect('trabajos.db')
cursor = conn.cursor()
query = """
SELECT order_code, line_number, line_status, estado_odoo, estado_fabricacion, order_date
FROM trabajos 
WHERE estado_interior_produccion = 'PENDIENTE' OR estado_tapa_produccion = 'PENDIENTE'
ORDER BY order_date DESC
"""
cursor.execute(query)
results = cursor.fetchall()
print(f"{'Order Code':<15} | {'Line':<4} | {'BMG Line Status':<25} | {'Odoo Status':<25} | {'Fab. Status':<20}")
print("-" * 105)
for row in results:
    print(f"{row[0]:<15} | {row[1]:<4} | {row[2] if row[2] else 'N/A':<25} | {row[3] if row[3] else 'N/A':<25} | {row[4] if row[4] else 'N/A':<20}")
conn.close()
