
import sqlite3
import json

def check_schema():
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obtener columnas de la tabla trabajos
    cursor.execute("PRAGMA table_info(trabajos)")
    columns = [row['name'] for row in cursor.fetchall()]
    print("COLUMNAS:")
    print(", ".join(columns))
    
    # Ver una muestra de datos_envio_json
    cursor.execute("SELECT datos_envio_json FROM trabajos WHERE datos_envio_json IS NOT NULL LIMIT 1")
    row = cursor.fetchone()
    if row:
        print("\nJSON DE ENVIO COMPLETO:")
        print(row['datos_envio_json'])
    
    conn.close()

if __name__ == "__main__":
    check_schema()
