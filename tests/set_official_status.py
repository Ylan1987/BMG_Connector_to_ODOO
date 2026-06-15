import sqlite3

def set_status_generado():
    try:
        conn = sqlite3.connect('trabajos.db')
        cursor = conn.cursor()
        
        # Cambiamos el estado inventado por uno oficial que los scripts 06 y 07 ignorarán (porque ya está "listo")
        cursor.execute("""
            UPDATE trabajos 
            SET estado_interior_produccion = 'GENERADO',
                estado_tapa_produccion = 'GENERADO'
        """)
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Actualización completada. {affected} líneas marcadas como 'GENERADO' en la base de datos.")
    except Exception as e:
        print(f"❌ Error al actualizar estados: {e}")

if __name__ == "__main__":
    set_status_generado()
