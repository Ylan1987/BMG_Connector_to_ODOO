import sqlite3
import os
import re

def corregir_db():
    print("Conectando a trabajos.db...")
    conn = sqlite3.connect('/app/trabajos.db') # Ruta dentro del contenedor Docker o servidor
    cursor = conn.cursor()
    
    # Buscar registros con estado GENERADO pero sin papel_tapa_size
    cursor.execute("SELECT order_code, line_number, ruta_archivo_tapa FROM trabajos WHERE estado_tapa_produccion = 'GENERADO' AND papel_tapa_size IS NULL")
    rows = cursor.fetchall()
    
    print(f"Se encontraron {len(rows)} registros para corregir.")
    actualizados = 0
    
    for row in rows:
        order_code, line_number, ruta_archivo_tapa = row
        if ruta_archivo_tapa:
            # Ejemplo de ruta: /salida/LAD/Tapas/663434-1_33x70x1_Libro del Maestro Masón.pdf
            # Extraemos el tamaño usando regex
            filename = os.path.basename(ruta_archivo_tapa)
            match = re.search(r'_(\d+x\d+(?:\.\d+)?)x', filename)
            if match:
                ps = match.group(1)
                cursor.execute('UPDATE trabajos SET papel_tapa_size = ? WHERE order_code = ? AND line_number = ?', (ps, order_code, line_number))
                print(f'  -> Actualizado {order_code}-{line_number} con tamaño {ps}')
                actualizados += 1
            else:
                print(f'  -> No se pudo extraer el tamaño de: {filename}')
    
    conn.commit()
    conn.close()
    print(f"\nFinalizado. Se actualizaron {actualizados} registros correctamente.")

if __name__ == "__main__":
    corregir_db()
