import sqlite3
import math
import os
import sys
from common import mapeos

# Usamos la base de datos configurada para el entorno
DB_PATH = mapeos.DB_FILE

def actualizar_layouts():
    print(f"Conectando a {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Buscamos los que no tengan interior_layout pero que ya hayan sido procesados por el viejo script 6
    cursor.execute("""
        SELECT order_code, line_number, width, height, quantity_requested 
        FROM trabajos 
        WHERE interior_layout IS NULL AND estado_interior_produccion = 'GENERADO'
    """)
    trabajos = cursor.fetchall()
    
    if not trabajos:
        print("No se encontraron trabajos que requieran actualizacion (interior_layout IS NULL).")
        conn.close()
        return

    print(f"Se encontraron {len(trabajos)} trabajos para actualizar.")
    
    actualizados = 0
    for t in trabajos:
        try:
            width_mm = float(t['width'] or 0)
            height_mm = float(t['height'] or 0)
            cantidad = int(t['quantity_requested'] or 1)
            
            orientacion = 'V' if height_mm >= width_mm else 'A'

            layout, papel_folder = ("1up", "23x32")
            if orientacion == 'V':
                if (width_mm <= 156 and height_mm <= 221): 
                    layout, papel_folder = ("2up", "23x32")
                elif (width_mm <= 171 and height_mm <= 241): 
                    layout, papel_folder = ("2up", "25x35")
            elif orientacion == 'A':
                if (width_mm <= 221 and (height_mm * 2) <= 312):
                    layout, papel_folder = ("2up", "23x32")

            # Cálculo de copias
            if layout == "2up" and (cantidad % 2 == 0 or cantidad >= 10):
                copias = math.ceil(cantidad / 2)
            else:
                copias = cantidad

            cursor.execute("""
                UPDATE trabajos 
                SET interior_layout = ?, interior_papel_folder = ?, copias_calculadas = ?
                WHERE order_code = ? AND line_number = ?
            """, (layout, papel_folder, copias, t['order_code'], t['line_number']))
            
            print(f" -> Actualizado {t['order_code']}-{t['line_number']} | Size: {width_mm}x{height_mm}mm | {layout} en {papel_folder} | Copias: {copias}")
            actualizados += 1
            
        except Exception as e:
            print(f"Error procesando {t['order_code']}-{t['line_number']}: {e}")

    conn.commit()
    conn.close()
    print(f"Finalizado. Se actualizaron {actualizados} trabajos exitosamente.")

if __name__ == '__main__':
    actualizar_layouts()
