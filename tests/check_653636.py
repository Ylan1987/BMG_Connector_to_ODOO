import sqlite3
import os

db_path = 'trabajos.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

search_term = '653636'
print(f"Searching for {search_term} in trabajos table...")

# Search in all columns just in case
cursor.execute("PRAGMA table_info(trabajos)")
columns = [col[1] for col in cursor.fetchall()]

where_clauses = [f"{col} LIKE ?" for col in columns]
query = f"SELECT * FROM trabajos WHERE {' OR '.join(where_clauses)}"
params = [f"%{search_term}%"] * len(columns)

cursor.execute(query, params)
rows = cursor.fetchall()

if not rows:
    print(f"No se encontró nada relacionado con {search_term} en la tabla trabajos")
else:
    print(f"Found {len(rows)} matching rows:")
    for row in rows:
        print(dict(row))

conn.close()
