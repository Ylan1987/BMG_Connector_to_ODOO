import sqlite3

def check_status_ids():
    conn = sqlite3.connect('trabajos.db')
    cursor = conn.cursor()
    query = """
    SELECT line_status, line_status_id, COUNT(*) 
    FROM trabajos 
    WHERE estado_interior_produccion = 'PENDIENTE' OR estado_tapa_produccion = 'PENDIENTE'
    GROUP BY line_status, line_status_id
    """
    cursor.execute(query)
    results = cursor.fetchall()
    print(f"{'Line Status':<25} | {'ID':<5} | {'Count':<5}")
    print("-" * 40)
    for row in results:
        print(f"{row[0] if row[0] else 'N/A':<25} | {row[1] if row[1] else 'N/A':<5} | {row[2]:<5}")
    conn.close()

if __name__ == "__main__":
    check_status_ids()
