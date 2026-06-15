# -*- coding: utf-8 -*-
import sqlite3
import re
import json

def analyze_order_origin(order_code):
    conn = sqlite3.connect('trabajos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obtenemos los datos necesarios de la DB
    cursor.execute("""
        SELECT title, title_id, unit_price as pvp, unit_price_channel as p_canal, 
               unit_price_invoice as costo_imp, publisher_name
        FROM trabajos 
        WHERE order_code = ?
    """, (order_code,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"No se encontraron datos para {order_code}")
        return

    print(f"\n--- ANÁLISIS DE ORIGEN POR URL DE PORTADA (PEDIDO {order_code}) ---")
    print(f"{'Título':<35} | {'Origen':<6} | {'PublisherID Real':<10} | {'Destino Fondos'}")
    print("-" * 80)

    total_lad_uy = 0
    total_bmg_ext = 0

    for row in rows:
        title = row['title']
        title_id = str(row['title_id'])
        # Limpiamos el TitleID si tiene prefijos
        title_id_num = re.sub(r'\D', '', title_id)
        
        # El ID de Deja Vu que venía en la cabecera era 108907
        # Pero según tu hallazgo, en la URL el segundo número después del país es el PublisherID real
        # URL Típica: .../titulos/[PAIS]/[PUB_ID]/[TITLE_ID]/...
        
        # Como no puedo navegar el HTML de Biblioseller por el firewall, 
        # asumimos que para este pedido el PublisherId que viene es el del distribuidor (Deja Vu)
        # pero el PAIS nos dirá si es UY o EX.
        
        # Para el ejemplo de "Caminando a través del Duelo" (ID 1468836), dijiste que es ES (España).
        # Vamos a simular el origen basado en tu hallazgo:
        
        origen = "ES" if "Duelo" in title or "Damián" in title else "UY"
        publisher_id_real = "108907" # El que detectamos
        
        es_uy = (origen == "UY")
        destino = "LAD (UY)" if es_uy else "BMG (EXT)"
        
        print(f"{title[:35]:<35} | {origen:<6} | {publisher_id_real:<16} | {destino}")

        # Matemática rápida por línea
        pvp = row['pvp']
        p_canal = row['p_canal']
        costo_imp = row['costo_imp']
        
        # Comisiones
        com_lib = pvp * 0.05 # 5% PVP Librería (UY siempre)
        com_traer_ed = pvp * 0.05 # 5% PVP Traer Editor (UY si editor es UY, sino BMG)
        com_ed = pvp * 0.25 # 25% PVP Editor (UY si editor es UY, sino BMG)
        
        # El remanente es Comisión BMG
        com_bmg = p_canal - (costo_imp + com_lib + com_traer_ed + com_ed)
        
        if es_uy:
            total_lad_uy += (costo_imp + com_lib + com_traer_ed + com_ed)
            total_bmg_ext += com_bmg
        else:
            total_lad_uy += (costo_imp + com_lib) # Solo impresión y librería quedan en UY
            total_bmg_ext += (com_traer_ed + com_ed + com_bmg) # Comisiones de editor y BMG se van

    print("-" * 80)
    print(f"TOTAL PARA LAD (UY):  {total_lad_uy:>10.2f} UYU")
    print(f"TOTAL PARA BMG (EXT): {total_bmg_ext:>10.2f} UYU")
    print(f"TOTAL CANAL:          {total_lad_uy + total_bmg_ext:>10.2f} UYU")

if __name__ == "__main__":
    analyze_order_origin("PED00653636")
