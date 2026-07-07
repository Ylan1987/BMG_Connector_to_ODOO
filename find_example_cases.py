import sqlite3
def get_examples():
    conn = sqlite3.connect('C:\\Users\\ylana\\Downloads\\BMG\\V2.0\\trabajos.db')
    cursor = conn.cursor()
    
    print("--- EJEMPLO 1: Cumple Editor, Cumple Tipo, NO Cumple Unidad de Negocio ---")
    cursor.execute("""
        SELECT DISTINCT order_code, publisher_facility, business_unit, order_type 
        FROM trabajos 
        WHERE publisher_facility != 'LAD'
        AND order_type NOT LIKE '%eDistrib%'
        AND business_unit NOT LIKE '%eDistribuc%'
        LIMIT 2
    """)
    rows1 = cursor.fetchall()
    for r in rows1:
        print(f"Pedido: {r[0]} | Editor: {r[1]} | BU: {r[2]} | Tipo: {r[3]}")
        
    print("\n--- EJEMPLO 2: Cumple Editor, Cumple Unidad de Negocio, NO Cumple Tipo ---")
    cursor.execute("""
        SELECT DISTINCT order_code, publisher_facility, business_unit, order_type 
        FROM trabajos 
        WHERE publisher_facility != 'LAD'
        AND business_unit LIKE '%eDistribuc%'
        AND order_type LIKE '%eDistrib%'
        LIMIT 2
    """)
    rows2 = cursor.fetchall()
    for r in rows2:
        print(f"Pedido: {r[0]} | Editor: {r[1]} | BU: {r[2]} | Tipo: {r[3]}")
        
    conn.close()

if __name__ == '__main__':
    get_examples()
