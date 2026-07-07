import sqlite3
def get_example():
    conn = sqlite3.connect('C:\\Users\\ylana\\Downloads\\BMG\\V2.0\\trabajos.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT order_code, publisher_facility, business_unit, order_type 
        FROM trabajos 
        WHERE publisher_facility != 'LAD'
        AND business_unit LIKE '%eDistribuc%'
        AND order_type NOT LIKE '%eDistrib%'
        LIMIT 5
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"Pedido: {r[0]} | Editor: {r[1]} | BU: {r[2]} | Tipo: {r[3]}")
    conn.close()

if __name__ == '__main__':
    get_example()
