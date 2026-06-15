import sqlite3

def reset_orders():
    orders = [
        "656631-1", "656643-1", "656636-1", "656636-2", "656645-1",
        "656650-1", "656650-2", "656646-1", "656673-1", "656682-1",
        "656753-1", "656754-1", "656801-1", "656801-7", "656801-8",
        "656801-10", "656801-14", "656801-15", "657017-1", "656635-1",
        "656714-1", "656751-1", "656799-1", "656801-2", "656801-3",
        "656801-4", "656801-5", "656801-6", "656801-9", "656801-11",
        "656801-12", "656801-13", "656801-16"
    ]

    conn = sqlite3.connect('trabajos.db')
    cursor = conn.cursor()

    updated_count = 0
    for order_str in orders:
        order_num, line_num = order_str.split('-')
        line_num = int(line_num)
        
        # Check if the order exists first
        cursor.execute(f"SELECT order_code, line_number FROM trabajos WHERE order_code LIKE '%{order_num}%' AND line_number = ?", (line_num,))
        rows = cursor.fetchall()
        
        if rows:
            for row in rows:
                actual_order_code = row[0]
                # Reset only PDF states, keeping Odoo states untouched
                cursor.execute(
                    "UPDATE trabajos SET estado_tapa_produccion = 'PENDIENTE', estado_interior_produccion = 'PENDIENTE' "
                    "WHERE order_code = ? AND line_number = ?", 
                    (actual_order_code, line_num)
                )
                print(f"✅ Reset PDF states for {actual_order_code} - Line {line_num}")
                updated_count += 1
        else:
            print(f"⚠️ Order {order_str} not found in database.")

    conn.commit()
    conn.close()
    print(f"\nTotal lines reset for PDF generation: {updated_count}")

if __name__ == "__main__":
    reset_orders()
