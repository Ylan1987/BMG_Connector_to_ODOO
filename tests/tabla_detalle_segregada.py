# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

def generate_full_detail_segregated_table():
    conn = sqlite3.connect('trabajos.db')
    query = """
    SELECT title, unit_price as pvp, unit_price_channel as p_canal, 
           unit_price_invoice as costo_imp, title_id
    FROM trabajos 
    WHERE order_code = 'PED00653636'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Todos son ES (España)
    pub_id = "108907"

    # Cálculos detallados por línea
    df['Costo Impres. (UY)'] = df['costo_imp']
    df['Comis. Traer Librería (UY)'] = df['pvp'] * 0.05
    
    # BMG Terceros (5% traer + 25% editor)
    df['Comis. Traer Editor (BMG-Terceros)'] = df['pvp'] * 0.05
    df['Comisión Editor (BMG-Terceros)'] = df['pvp'] * 0.25
    df['TOTAL BMG A CUENTA DE TERCEROS'] = df['Comis. Traer Editor (BMG-Terceros)'] + df['Comisión Editor (BMG-Terceros)']
    
    # BMG Propio (Saldo)
    # Saldo = Canal - Impresion - Lib - BMG Terceros
    df['TOTAL BMG PROPIO (SALDO)'] = df['p_canal'] - (
        df['Costo Impres. (UY)'] + 
        df['Comis. Traer Librería (UY)'] + 
        df['TOTAL BMG A CUENTA DE TERCEROS']
    )

    # Total LAD (UY)
    df['TOTAL LAD (UY)'] = df['Costo Impres. (UY)'] + df['Comis. Traer Librería (UY)']

    # URL Portada
    df['URL Portada'] = df['title_id'].apply(lambda tid: f"https://canal.bibliomanager.com/titulos/ES/143/{pub_id}/{tid}/{tid}_IMAGEN_TAPA_G_002.jpg")

    # Formateo
    pd.options.display.float_format = '{:,.2f}'.format
    pd.options.display.max_columns = None
    pd.options.display.width = 1000
    
    print("\n" + "="*160)
    print("MATEMÁTICA DETALLADA CON SEGREGACIÓN BMG - PEDIDO 653636")
    print("="*160)
    
    cols_show = [
        'title', 'p_canal', 'Costo Impres. (UY)', 'Comis. Traer Librería (UY)', 
        'TOTAL BMG A CUENTA DE TERCEROS', 'TOTAL BMG PROPIO (SALDO)', 
        'TOTAL LAD (UY)', 'URL Portada'
    ]
    
    print(df[cols_show].to_string(index=False))
    
    print("\n" + "="*80)
    print(f"RESUMEN FINAL DE DISTRIBUCIÓN:")
    print(f"TOTAL LAD (UY):                   {df['TOTAL LAD (UY)'].sum():>10.2f} UYU")
    print(f"TOTAL BMG A CUENTA DE TERCEROS:    {df['TOTAL BMG A CUENTA DE TERCEROS'].sum():>10.2f} UYU")
    print(f"TOTAL BMG PROPIO (SALDO):          {df['TOTAL BMG PROPIO (SALDO)'].sum():>10.2f} UYU")
    print("-" * 80)
    print(f"TOTAL PRECIO CANAL:                {df['p_canal'].sum():>10.2f} UYU")
    print("="*80)

if __name__ == "__main__":
    generate_full_detail_segregated_table()
