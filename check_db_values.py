import sqlite3

def check_db():
    conn = sqlite3.connect('C:\\Users\\ylana\\Downloads\\BMG\\V2.0\\trabajos.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT order_type, business_unit, publisher_facility FROM trabajos")
    rows = cursor.fetchall()
    for r in rows:
        print(r)
    conn.close()

if __name__ == '__main__':
    check_db()
