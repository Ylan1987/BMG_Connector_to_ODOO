import sqlite3

def deep_inspect():
    conn = sqlite3.connect('trabajos.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Tables: {tables}")
    
    for table in tables:
        print(f"\n--- Schema for {table} ---")
        cursor.execute(f"PRAGMA table_info({table})")
        for col in cursor.fetchall():
            print(col)
            
    # Buscar si hay alguna otra tabla con 'log' o 'history'
    # No parece haber por los nombres.
    
    conn.close()

if __name__ == "__main__":
    deep_inspect()
