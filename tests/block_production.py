import sqlite3

def block_historical_production():
    try:
        conn = sqlite3.connect('trabajos.db')
        cursor = conn.cursor()
        
        # Bloqueo total de producción para registros existentes
        cursor.execute("""
            UPDATE trabajos 
            SET estado_interior_produccion = 'OMITIDO_HISTORICO',
                estado_tapa_produccion = 'OMITIDO_HISTORICO'
        """)
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Bloqueo completado. {affected} líneas marcadas como OMITIDO_HISTORICO en la base de datos.")
    except Exception as e:
        print(f"❌ Error al bloquear: {e}")

if __name__ == "__main__":
    block_historical_production()
