# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

def generate_ultra_detail_table():
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

    # 1. Componentes UY (LAD)
    df['Costo Impres. (UY)'] = df['costo_imp']
    df['Comis. Tr. Librería (UY)'] = df['pvp'] * 0.05
    
    # 2. Componentes BMG a cuenta de Terceros (Origen ES)
    df['Comisión Editor (BMG)'] = df['pvp'] * 0.25
    df['Comis. Tr. Editor (BMG)'] = df['pvp'] * 0.05
    df['Total BMG Terceros'] = df['Comisión Editor (BMG)'] + df['Comis. Tr. Editor (BMG)']
    
    # 3. Componente BMG Propio (Saldo)
    # Saldo = Canal - (Impresion + Lib + BMG Terceros)
    df['Total BMG Propio (Saldo)'] = df['p_canal'] - (
        df['Costo Impres. (UY)'] + 
        df['Comis. Tr. Librería (UY)'] + 
        df['Total BMG Terceros']
    )

    # Verificación de fila: Suma UY + BMG Terceros + BMG Propio = Canal
    df['Suma Verif.'] = df['Costo Impres. (UY)'] + df['Comis. Tr. Librería (UY)'] + df['Total BMG Terceros'] + df['Total BMG Propio (Saldo)']

    # URL Portada
    df['URL Portada'] = df['title_id'].apply(lambda tid: f"https://canal.bibliomanager.com/titulos/ES/143/{pub_id}/{tid}/{tid}_IMAGEN_TAPA_G_002.jpg")

    # Formateo
    pd.options.display.float_format = '{:,.2f}'.format
    pd.options.display.max_columns = None
    pd.options.display.width = 1200
    
    print("\n" + "="*180)
    print("MATEMÁTICA ULTRA DETALLADA - PEDIDO 653636")
    print("="*180)
    
    cols_show = [
        'title', 'p_canal', 'Costo Impres. (UY)', 'Comis. Tr. Librería (UY)', 
        'Comisión Editor (BMG)', 'Comis. Tr. Editor (BMG)', 'Total BMG Terceros', 
        'Total BMG Propio (Saldo)', 'URL Portada'
    ]
    
    print(df[cols_show].to_string(index=False))
    
    print("\n" + "="*80)
    print(f"RESUMEN FINAL DE DISTRIBUCIÓN:")
    print(f"TOTAL LAD (UY) [Impresión + Lib]:    { (df['Costo Impres. (UY)'] + df['Comis. Tr. Librería (UY)']).sum():>10.2f} UYU")
    print(f"TOTAL BMG A CUENTA DE TERCEROS:      {df['Total BMG Terceros'].sum():>10.2f} UYU")
    print(f"TOTAL BMG PROPIO (SALDO):            {df['Total BMG Propio (Saldo)'].sum():>10.2f} UYU")
    print("-" * 80)
    print(f"TOTAL PRECIO CANAL:                  {df['p_canal'].sum():>10.2f} UYU")
    print("="*80)

if __name__ == "__main__":
    generate_ultra_detail_table()
