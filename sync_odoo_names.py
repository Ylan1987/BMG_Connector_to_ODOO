import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import odoo_conn

def sync_names():
    print("--- Sincronizando nombres de Odoo (S00...) hacia la base de datos local ---")
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        print("❌ Error de conexión a Odoo")
        return
        
    from common import db_conn
    conn = db_conn.conectar_db()
    if not conn: return
    cursor = conn.cursor()
    
    # Buscar todos los que tienen ID pero no tienen NAME
    cursor.execute("SELECT DISTINCT odoo_sale_order_id FROM trabajos WHERE odoo_sale_order_id IS NOT NULL AND (odoo_sale_order_name IS NULL OR odoo_sale_order_name = '')")
    ids_faltantes = [row[0] for row in cursor.fetchall() if row[0]]
    
    if not ids_faltantes:
        print("✅ No hay nombres faltantes.")
        conn.close()
        return
        
    print(f"⚠️ Se encontraron {len(ids_faltantes)} pedidos sin su nombre 'S00...' en la base. Descargando en lote...")
    
    # Partir en bloques de 1000 por si son muchos
    chunk_size = 1000
    actualizados = 0
    for i in range(0, len(ids_faltantes), chunk_size):
        chunk = ids_faltantes[i:i+chunk_size]
        try:
            resultados = odoo_api.execute('sale.order', 'search_read', [('id', 'in', chunk)], ['id', 'name'])
            
            # Preparar datos para UPDATE masivo
            ups = [(r['name'], r['id']) for r in resultados if r.get('name')]
            
            if ups:
                cursor.executemany("UPDATE trabajos SET odoo_sale_order_name = ? WHERE odoo_sale_order_id = ?", ups)
                conn.commit()
                actualizados += len(ups)
                print(f"  -> Lote {i//chunk_size + 1}: {len(ups)} nombres guardados.")
        except Exception as e:
            print(f"❌ Error en lote {i//chunk_size + 1}: {e}")
            
    conn.close()
    print(f"✅ Proceso terminado. Se guardaron {actualizados} nombres S00... oficiales en la base de datos.")

if __name__ == '__main__':
    sync_names()
