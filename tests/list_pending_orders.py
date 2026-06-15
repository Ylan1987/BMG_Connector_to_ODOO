import sqlite3
conn = sqlite3.connect('trabajos.db')
cursor = conn.cursor()
query = """
SELECT order_code, line_number, order_date, estado_interior_produccion, estado_tapa_produccion 
FROM trabajos 
WHERE estado_interior_produccion = 'PENDIENTE' OR estado_tapa_produccion = 'PENDIENTE'
ORDER BY order_date DESC
"""
cursor.execute(query)
results = cursor.fetchall()
print(f"{'Order Code':<15} | {'Line':<4} | {'Order Date':<20} | {'Int. Status':<12} | {'Tapa Status':<12}")
print("-" * 75)
for row in results:
    print(f"{row[0]:<15} | {row[1]:<4} | {row[2]:<20} | {row[3]:<12} | {row[4]:<12}")
conn.close()
