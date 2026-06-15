# -*- coding: utf-8 -*-
import sqlite3
import json

def ver_columnas():
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(trabajos)")
    columnas = [row['name'] for row in cursor.fetchall()]
    print(f"Columnas en 'trabajos': {columnas}")
    
    cursor.execute("SELECT * FROM trabajos LIMIT 1")
    row = cursor.fetchone()
    if row:
        print("\nEjemplo de datos (primera fila):")
        for col in columnas:
            print(f"  {col}: {row[col]}")
    conn.close()

if __name__ == "__main__":
    ver_columnas()
