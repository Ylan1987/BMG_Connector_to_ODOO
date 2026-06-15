# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

def generate_final_table():
    conn = sqlite3.connect('trabajos.db')
    query = """
    SELECT title, unit_price as pvp, unit_price_channel as p_canal, 
           unit_price_invoice as costo_imp
    FROM trabajos 
    WHERE order_code = 'PED00653636'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Definimos el origen basado en el hallazgo del usuario
    # ES = España (BMG), UY = Uruguay (LAD)
    # El usuario mencionó DAMIÁN (ES) y Duelo (ES)
    def get_origin(title):
        t = title.lower()
        if "damián" in t or "duelo" in t:
            return "ES"
        return "UY"

    df['Origen'] = df['title'].apply(get_origin)

    # 1. Costo impresión (UY) - Siempre queda en UY (LAD)
    df['Costo Impres. (UY)'] = df['costo_imp']

    # 2. 5% PVP Comisión Librería (UY) - Siempre queda en UY
    df['Comis. Librería (UY)'] = df['pvp'] * 0.05

    # 3. 5% PVP Comisión traer Editor
    df['Comis. Traer Ed. (UY)'] = df.apply(lambda r: r['pvp'] * 0.05 if r['Origen'] == "UY" else 0, axis=1)
    df['Comis. Traer Ed. (BMG)'] = df.apply(lambda r: r['pvp'] * 0.05 if r['Origen'] == "ES" else 0, axis=1)

    # 4. 25% PVP Comisión Editor
    df['Comis. Editor (UY)'] = df.apply(lambda r: r['pvp'] * 0.25 if r['Origen'] == "UY" else 0, axis=1)
    df['Comis. Editor (BMG)'] = df.apply(lambda r: r['pvp'] * 0.25 if r['Origen'] == "ES" else 0, axis=1)

    # 5. Comisión BMG (Remanente del Precio Canal)
    # Canal - CostoImp - ComLib - ComTraer - ComEd
    df['Comis. BMG (BMG)'] = df['p_canal'] - (
        df['Costo Impres. (UY)'] + 
        df['Comis. Librería (UY)'] + 
        df['Comis. Traer Ed. (UY)'] + df['Comis. Traer Ed. (BMG)'] + 
        df['Comis. Editor (UY)'] + df['Comis. Editor (BMG)']
    )

    # Totales LAD y BMG
    df['TOTAL LAD (UY)'] = (
        df['Costo Impres. (UY)'] + 
        df['Comis. Librería (UY)'] + 
        df['Comis. Traer Ed. (UY)'] + 
        df['Comis. Editor (UY)']
    )
    
    df['TOTAL BMG (BMG)'] = (
        df['Comis. Traer Ed. (BMG)'] + 
        df['Comis. Editor (BMG)'] + 
        df['Comis. BMG (BMG)']
    )

    # Formateo y visualización
    pd.options.display.float_format = '{:,.2f}'.format
    print("\n--- MATEMÁTICA FINAL PEDIDO 653636 (Basado en Origen de Portada) ---")
    
    cols = [
        'title', 'Origen', 'p_canal', 'Costo Impres. (UY)', 'Comis. Librería (UY)',
        'Comis. Traer Ed. (UY)', 'Comis. Traer Ed. (BMG)', 
        'Comis. Editor (UY)', 'Comis. Editor (BMG)',
        'Comis. BMG (BMG)', 'TOTAL LAD (UY)', 'TOTAL BMG (BMG)'
    ]
    
    print(df[cols].to_string(index=False))
    
    print("\n" + "="*50)
    print(f"RESUMEN DE FONDOS DEL PEDIDO:")
    print(f"PLATA PARA LAD (UY):  {df['TOTAL LAD (UY)'].sum():>10.2f} UYU")
    print(f"PLATA PARA BMG (BMG): {df['TOTAL BMG (BMG)'].sum():>10.2f} UYU")
    print(f"TOTAL PRECIO CANAL:   {df['p_canal'].sum():>10.2f} UYU")
    print("="*50)

if __name__ == "__main__":
    generate_final_table()
