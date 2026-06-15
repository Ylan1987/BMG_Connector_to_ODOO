# -*- coding: utf-8 -*-
import sqlite3
import requests
import pandas as pd
import re

def get_real_image_url(country, pub_id, title_id):
    # Estructura de URL proporcionada por el usuario
    # https://canal.bibliomanager.com/titulos/ES/143/108907/1468836/1468836_IMAGEN_TAPA_G_002.jpg
    # Intentaremos con la estructura que parece ser la estándar
    return f"https://canal.bibliomanager.com/titulos/{country}/143/{pub_id}/{title_id}/{title_id}_IMAGEN_TAPA_G_002.jpg"

def verify_and_analyze():
    conn = sqlite3.connect('trabajos.db')
    query = "SELECT title, title_id, unit_price as pvp, unit_price_channel as p_canal, unit_price_invoice as costo_imp, publisher_id FROM trabajos WHERE order_code = 'PED00653636'"
    df = pd.read_sql_query(query, conn)
    conn.close()

    results = []
    
    print("\n--- VERIFICANDO PORTADAS EN VIVO ---")
    
    for _, row in df.iterrows():
        title = row['title']
        title_id = str(row['title_id'])
        pub_id = "108907" # El PublisherId que detectamos en el XML para Deja Vu
        
        # Probamos primero ES (España) y luego UY (Uruguay)
        found_country = "DESCONOCIDO"
        final_url = ""
        
        for country in ["ES", "UY"]:
            url = get_real_image_url(country, pub_id, title_id)
            try:
                # Usamos HEAD para no descargar toda la imagen, solo verificar si existe (200 OK)
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    found_country = country
                    final_url = url
                    break
            except:
                pass
        
        print(f"Título: {title[:30]}... | Detectado: {found_country}")
        
        # Cálculos matemáticos
        pvp = row['pvp']
        p_canal = row['p_canal']
        costo_imp = row['costo_imp']
        
        es_uy = (found_country == "UY")
        
        com_lib = pvp * 0.05
        com_traer = pvp * 0.05
        com_ed = pvp * 0.25
        
        # Si es UY, comisiones quedan en UY. Si es ES (o no encontrado), se van a BMG.
        if es_uy:
            total_lad = costo_imp + com_lib + com_traer + com_ed
            com_bmg_val = p_canal - total_lad
            total_bmg = com_bmg_val
            c_traer_label = "UY"
            c_ed_label = "UY"
        else:
            total_lad = costo_imp + com_lib
            com_bmg_val = p_canal - (total_lad + com_traer + com_ed)
            total_bmg = com_traer + com_ed + com_bmg_val
            c_traer_label = "BMG"
            c_ed_label = "BMG"

        results.append({
            'Título': title,
            'Origen': found_country,
            'URL Portada': final_url,
            'P. Canal': p_canal,
            'Costo Imp (UY)': costo_imp,
            'Com Lib (UY)': com_lib,
            f'Com Traer ({c_traer_label})': com_traer,
            f'Com Editor ({c_ed_label})': com_ed,
            'Com BMG (BMG)': com_bmg_val,
            'TOTAL LAD (UY)': total_lad,
            'TOTAL BMG (BMG)': total_bmg
        })

    # Generar tabla final
    final_df = pd.DataFrame(results)
    pd.options.display.max_colwidth = 60
    pd.options.display.float_format = '{:,.2f}'.format
    
    print("\n" + "="*120)
    print("TABLA FINAL DE COMISIONES - PEDIDO 653636")
    print("="*120)
    print(final_df.to_string(index=False))
    
    print("\n" + "="*50)
    print(f"RESUMEN FINAL:")
    print(f"TOTAL LAD (UY):  {final_df['TOTAL LAD (UY)'].sum():>10.2f} UYU")
    print(f"TOTAL BMG (BMG): {final_df['TOTAL BMG (BMG)'].sum():>10.2f} UYU")
    print(f"TOTAL CANAL:     {final_df['P. Canal'].sum():>10.2f} UYU")
    print("="*50)

if __name__ == "__main__":
    verify_and_analyze()
