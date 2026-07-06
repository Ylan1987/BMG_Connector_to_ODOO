import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import db_conn

def resetear_pedido():
    # Podés cambiar esta lista si necesitás probar con otros
    PEDIDOS_A_RESETEAR = ['PED00664005', 'PED00663995']
    
    conn = db_conn.conectar_db()
    if not conn:
        print("❌ No se pudo conectar a la base de datos.")
        return
        
    cursor = conn.cursor()
    
    try:
        for pedido in PEDIDOS_A_RESETEAR:
            # Resetear los flags de PDF generado
            cursor.execute("""
                UPDATE trabajos 
                SET estado_interior_produccion = 'PENDIENTE', 
                    estado_tapa_produccion = 'PENDIENTE' 
                WHERE order_code = ?
            """, (pedido,))
            
            filas_afectadas = cursor.rowcount
            
            if filas_afectadas > 0:
                print(f"✅ ÉXITO: El pedido {pedido} fue reseteado ({filas_afectadas} líneas).")
            else:
                print(f"⚠️ ATENCIÓN: No se encontró el pedido {pedido} en la base de datos.")
        
        conn.commit()
        print("\nAhora podés volver a correr el orquestador y los va a procesar desde cero.")
            
    except Exception as e:
        print(f"❌ Error al resetear el pedido: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    resetear_pedido()
