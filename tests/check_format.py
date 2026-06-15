import sqlite3

def check_format():
    old_conn = sqlite3.connect('trabajosViejos.db')
    new_conn = sqlite3.connect('trabajos.db')
    
    print("Old DB sample order_code:")
    print(old_conn.execute("SELECT order_code FROM trabajos LIMIT 5").fetchall())
    
    print("New DB sample order_code:")
    print(new_conn.execute("SELECT order_code FROM trabajos LIMIT 5").fetchall())
    
    old_conn.close()
    new_conn.close()

check_format()
