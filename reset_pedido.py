import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import db_conn

def resetear_pedido():
    # Podés cambiar el PEDIDO_A_RESETEAR si necesitás probar con otro
    PEDIDO_A_RESETEAR = 'PED00663377'
    
    conn = db_conn.conectar_db()
    if not conn:
        print("❌ No se pudo conectar a la base de datos.")
        return
        
    cursor = conn.cursor()
    
    try:
        # Resetear los flags de PDF generado
        cursor.execute("""
            UPDATE trabajos 
            SET pdf_interior_generado = 0, 
                pdf_tapa_generado = 0 
            WHERE order_code = ?
        """, (PEDIDO_A_RESETEAR,))
        
        filas_afectadas = cursor.rowcount
        conn.commit()
        
        if filas_afectadas > 0:
            print(f"✅ ÉXITO: El pedido {PEDIDO_A_RESETEAR} fue reseteado ({filas_afectadas} líneas).")
            print("Ahora podés volver a correr el Script 06 (Interior) y Script 07 (Tapa) y lo van a volver a procesar.")
        else:
            print(f"⚠️ ATENCIÓN: No se encontró el pedido {PEDIDO_A_RESETEAR} en la base de datos.")
            
    except Exception as e:
        print(f"❌ Error al resetear el pedido: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    resetear_pedido()
