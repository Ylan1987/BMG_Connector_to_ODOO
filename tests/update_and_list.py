import sqlite3

def update_specific_orders():
    orders_to_mark = [
        'PED00655805', 'PED00655795', 'PED00655774', 'PED00655757', 'PED00655755'
    ]
    
    new_conn = sqlite3.connect('trabajos.db')
    new_cursor = new_conn.cursor()
    
    updated_count = 0
    for order_code in orders_to_mark:
        new_cursor.execute("""
            UPDATE trabajos 
            SET estado_interior_produccion = 'GENERADO', 
                estado_tapa_produccion = 'GENERADO'
            WHERE order_code = ?
        """, (order_code,))
        updated_count += new_cursor.rowcount
        if new_cursor.rowcount > 0:
            print(f"Marked as GENERADO: {order_code}")
            
    new_conn.commit()
    print(f"\nSuccessfully updated {updated_count} rows in 'trabajos.db'.")
    
    # Generate new table
    query = """
    SELECT order_code, line_number, order_date, line_status, estado_odoo, estado_fabricacion
    FROM trabajos 
    WHERE estado_interior_produccion = 'PENDIENTE' OR estado_tapa_produccion = 'PENDIENTE'
    ORDER BY order_date DESC
    """
    new_cursor.execute(query)
    results = new_cursor.fetchall()
    
    print("\n--- UPDATED PENDING ORDERS TABLE ---")
    print(f"{'Order Code':<15} | {'Line':<4} | {'Order Date':<12} | {'BMG Status':<22} | {'Fab. Status':<15}")
    print("-" * 80)
    for row in results:
        # Format date for readability if it's long, or keep as is
        display_date = str(row[2])[:10] if row[2] else 'N/A'
        print(f"{row[0]:<15} | {row[1]:<4} | {display_date:<12} | {row[3] if row[3] else 'N/A':<22} | {row[5] if row[5] else 'N/A':<15}")
    
    new_conn.close()

if __name__ == "__main__":
    update_specific_orders()
