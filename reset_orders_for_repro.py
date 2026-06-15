import sqlite3

def reset_orders():
    orders_to_reset = [
        ('PED00656682', 1),
        ('PED00656673', 1),
        ('PED00656646', 1),
        ('PED00656645', 1),
        ('PED00656636', 2),
        ('PED00656636', 1),
        ('PED00656643', 1),
        ('PED00656635', 1),
        ('PED00656631', 1)
    ]
    
    conn = sqlite3.connect('trabajos.db')
    cursor = conn.cursor()
    
    updated_count = 0
    for order_code, line_number in orders_to_reset:
        cursor.execute("""
            UPDATE trabajos 
            SET estado_tapa_produccion = 'PENDIENTE',
                estado_interior_produccion = 'PENDIENTE',
                ruta_archivo_tapa = NULL,
                ruta_archivo_contenido = NULL
            WHERE order_code = ? AND line_number = ?
        """, (order_code, line_number))
        updated_count += cursor.rowcount
        print(f"Reset: {order_code}-{line_number}")
            
    conn.commit()
    print(f"\nSuccessfully reset {updated_count} rows in 'trabajos.db'.")
    conn.close()

if __name__ == "__main__":
    reset_orders()
