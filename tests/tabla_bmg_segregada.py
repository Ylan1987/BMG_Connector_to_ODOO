# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

def generate_final_split_table():
    conn = sqlite3.connect('trabajos.db')
    query = """
    SELECT title, title_id, unit_price as pvp, unit_price_channel as p_canal, 
           unit_price_invoice as costo_imp
    FROM trabajos 
    WHERE order_code = 'PED00653636'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Todos son ES (España) según la verificación de portadas
    df['Origen'] = "ES"
    pub_id = "108907"

    # 1. Costo impresión (UY)
    df['Costo Impres. (UY)'] = df['costo_imp']

    # 2. 5% PVP Comisión traer Librería (UY)
    df['Comis. Traer Librería (UY)'] = df['pvp'] * 0.05

    # 3. 5% PVP Comisión traer Editorial (BMG Terceros ya que es ES)
    df['Comis. Traer Editorial (BMG)'] = df['pvp'] * 0.05

    # 4. 25% PVP Comisión Editor (BMG Terceros ya que es ES)
    df['Comisión Editor (BMG)'] = df['pvp'] * 0.25

    # 5. Comis. BMG Propia (Remanente)
    df['Comis. BMG Propia (BMG)'] = df['p_canal'] - (
        df['Costo Impres. (UY)'] + 
        df['Comis. Traer Librería (UY)'] + 
        df['Comis. Traer Editorial (BMG)'] + 
        df['Comisión Editor (BMG)']
    )

    # Agrupación de Totales según lo pedido
    # TOTAL LAD: Lo que queda en UY
    df['TOTAL LAD (UY)'] = df['Costo Impres. (UY)'] + df['Comis. Traer Librería (UY)']
    
    # TOTAL BMG Terceros: 5% traer editor + 25% comisión editor (porque son extranjeros)
    df['Total BMG a cuenta de terceros (BMG)'] = df['Comis. Traer Editorial (BMG)'] + df['Comisión Editor (BMG)']
    
    # TOTAL BMG Propio: El saldo
    df['Total BMG propio (BMG)'] = df['Comis. BMG Propia (BMG)']

    # Construir URL de Portada para la tabla
    df['URL Portada'] = df['title_id'].apply(lambda tid: f"https://canal.bibliomanager.com/titulos/ES/143/{pub_id}/{tid}/{tid}_IMAGEN_TAPA_G_002.jpg")

    # Formateo
    pd.options.display.float_format = '{:,.2f}'.format
    print("\n--- MATEMÁTICA DEFINITIVA CON DESGLOSE DE BMG (PEDIDO 653636) ---")
    
    cols_show = [
        'title', 'Costo Impres. (UY)', 'Comis. Traer Librería (UY)', 
        'Total BMG a cuenta de terceros (BMG)', 'Total BMG propio (BMG)', 
        'TOTAL LAD (UY)', 'URL Portada'
    ]
    
    print(final_table := df[cols_show].to_string(index=False))
    
    print("\n" + "="*80)
    print(f"RESUMEN FINAL DE DISTRIBUCIÓN:")
    print(f"TOTAL LAD (UY):                   {df['TOTAL LAD (UY)'].sum():>10.2f} UYU")
    print(f"TOTAL BMG A CUENTA DE TERCEROS:    {df['Total BMG a cuenta de terceros (BMG)'].sum():>10.2f} UYU")
    print(f"TOTAL BMG PROPIO (SALDO):          {df['Total BMG propio (BMG)'].sum():>10.2f} UYU")
    print("-" * 80)
    print(f"TOTAL PRECIO CANAL:                {df['p_canal'].sum():>10.2f} UYU")
    print("="*80)

if __name__ == "__main__":
    generate_split_table = generate_final_split_table()
