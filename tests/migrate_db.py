
import sqlite3

def migrate():
    conn = sqlite3.connect('trabajos.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(trabajos)")
    columns = [row[1] for row in c.fetchall()]
    if 'meli_status' not in columns:
        print("Añadiendo columna 'meli_status'...")
        c.execute('ALTER TABLE trabajos ADD COLUMN meli_status TEXT')
        conn.commit()
    else:
        print("La columna 'meli_status' ya existe.")
    conn.close()

if __name__ == "__main__":
    migrate()
