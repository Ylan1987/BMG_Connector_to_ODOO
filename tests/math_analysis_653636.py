# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

def calculate_commissions():
    conn = sqlite3.connect('trabajos.db')
    query = """
    SELECT title, unit_price as pvp, unit_price_channel as p_canal, 
           unit_price_invoice as costo_imp, publisher_name
    FROM trabajos 
    WHERE order_code = 'PED00653636'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Supongamos que el editor es Uruguayo para este ejemplo (LAD)
    # En producción esto se compararía contra una lista de IDs uruguayos
    es_uruguayo = True 

    # 1. Costo impresión (UY)
    df['Costo Impresión (UY)'] = df['costo_imp']

    # 2. 5% PVP Comisión traer Librería (UY)
    df['Comisión Librería (UY)'] = df['pvp'] * 0.05

    # 3. 5% PVP Comisión traer Editor
    col_traer_ed = 'Comisión Traer Editor (UY)' if es_uruguayo else 'Comisión Traer Editor (BMG)'
    df[col_traer_ed] = df['pvp'] * 0.05

    # 4. 25% PVP Comisión Editor
    col_ed = 'Comisión Editor (UY)' if es_uruguayo else 'Comisión Editor (BMG)'
    df[col_ed] = df['pvp'] * 0.25

    # 5. Comisión BMG (Resto)
    # Diferencia = p_canal - costo_imp - com_lib - com_traer_ed - com_ed
    # Sumamos los valores sin importar el título de la columna
    df['Comisión BMG (BMG)'] = df['p_canal'] - (
        df['Costo Impresión (UY)'] + 
        df['Comisión Librería (UY)'] + 
        df[col_traer_ed] + 
        df[col_ed]
    )

    # Totales
    df['TOTAL LAD (UY)'] = df['Costo Impresión (UY)'] + df['Comisión Librería (UY)'] + df[col_traer_ed] + df[col_ed]
    df['TOTAL BMG (BMG)'] = df['Comisión BMG (BMG)']
    
    # Verificación
    df['Suma Verificación'] = df['TOTAL LAD (UY)'] + df['TOTAL BMG (BMG)']

    # Formatear para imprimir
    pd.options.display.float_format = '{:,.2f}'.format
    print("\n--- MATEMÁTICA PURA PEDIDO 653636 ---")
    print(f"Editor: {df['publisher_name'].iloc[0]} (Asumido {'Uruguayo' if es_uruguayo else 'Extranjero'})")
    
    cols_to_show = [
        'title', 'p_canal', 'Costo Impresión (UY)', 'Comisión Librería (UY)', 
        col_traer_ed, col_ed, 'Comisión BMG (BMG)', 'TOTAL LAD (UY)', 'TOTAL BMG (BMG)'
    ]
    print(df[cols_to_show].to_string(index=False))

if __name__ == "__main__":
    calculate_commissions()
