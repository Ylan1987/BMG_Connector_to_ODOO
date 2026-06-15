# -*- coding: utf-8 -*-
import sqlite3
import requests
import re
import time
import os
import sys

# Asegurar que podemos importar desde el directorio actual
sys.path.append(os.getcwd())

from common import mapeos, db_conn

def detectar_origen_por_url(title_id):
    """
    Detecta si un libro es de Uruguay (UY) o España (ES) verificando la URL de su portada.
    """
    pub_id_test = "108907" 
    title_id_num = "".join(filter(str.isdigit, str(title_id)))
    
    for country in ["ES", "UY"]:
        url = f"https://canal.bibliomanager.com/titulos/{country}/143/{pub_id_test}/{title_id_num}/{title_id_num}_IMAGEN_TAPA_G_002.jpg"
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                return country
        except:
            continue
    return "ES" # Por defecto ES

def safe_float(value):
    if not value: return 0.0
    try:
        # Quitamos comas si existen (ej: 1,225.00 -> 1225.00)
        clean_val = str(value).replace(',', '')
        return float(clean_val)
    except:
        return 0.0

def calcular_matematica_pura(row):
    """
    Realiza los cálculos de comisiones basados en el origen y los precios de una fila de la DB.
    """
    pvp = safe_float(row['unit_price'])
    p_canal = safe_float(row['unit_price_channel'])
    costo_imp = safe_float(row['unit_price_invoice'])
    
    origen = detectar_origen_por_url(row['title_id'])
    es_uy = (origen == "UY")
    
    # Comisiones estándar
    com_lib = pvp * 0.05
    com_traer_ed = pvp * 0.05
    com_editor = pvp * 0.25
    
    # Distribución según origen
    res = {
        'x_origen_pais': origen,
        'x_precio_canal': p_canal,
        'x_costo_impresion_uy': costo_imp,
        'x_comision_traer_libreria_uy': com_lib,
        'x_comision_traer_editor_uy': com_traer_ed if es_uy else 0,
        'x_comision_editor_uy': com_editor if es_uy else 0,
        'x_comision_traer_editor_bmg': 0 if es_uy else com_traer_ed,
        'x_comision_editor_bmg': 0 if es_uy else com_editor,
    }
    
    # Totales
    if es_uy:
        res['x_total_lad_uy'] = costo_imp + com_lib + com_traer_ed + com_editor
        res['x_total_bmg_terceros'] = 0
    else:
        res['x_total_lad_uy'] = costo_imp + com_lib
        res['x_total_bmg_terceros'] = com_traer_ed + com_editor
        
    res['x_comision_bmg_propia'] = p_canal - (res['x_total_lad_uy'] + res['x_total_bmg_terceros'])
    res['x_total_bmg_propio'] = res['x_comision_bmg_propia']
    
    return res

def migrate():
    print("--- Iniciando Migración de Datos Financieros para eDist ---")
    conn = db_conn.conectar_db()
    if not conn:
        print("No se pudo conectar a la base de datos.")
        return
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscamos todos los pedidos de eDist que no tengan calculado el origen todavía
    query_select = f"SELECT * FROM trabajos WHERE order_type LIKE '%{mapeos.BMG_ORDER_TYPE_EDIST}%' AND (x_origen_pais IS NULL OR x_origen_pais = '')"
    cursor.execute(query_select)
    rows = cursor.fetchall()
    
    print(f"Se encontraron {len(rows)} líneas para actualizar.")
    
    actualizados = 0
    for row in rows:
        order_code = row['order_code']
        line_number = row['line_number']
        title = row['title']
        
        print(f"  -> Procesando {order_code}-{line_number}: {title[:30]}...")
        
        try:
            res = calcular_matematica_pura(row)
            
            update_query = """
                UPDATE trabajos SET
                    x_origen_pais = ?,
                    x_precio_canal = ?,
                    x_costo_impresion_uy = ?,
                    x_comision_traer_libreria_uy = ?,
                    x_comision_traer_editor_uy = ?,
                    x_comision_editor_uy = ?,
                    x_comision_traer_editor_bmg = ?,
                    x_comision_editor_bmg = ?,
                    x_comision_bmg_propia = ?,
                    x_total_bmg_terceros = ?,
                    x_total_bmg_propio = ?,
                    x_total_lad_uy = ?
                WHERE order_code = ? AND line_number = ?
            """
            
            cursor.execute(update_query, (
                res['x_origen_pais'], res['x_precio_canal'], res['x_costo_impresion_uy'],
                res['x_comision_traer_libreria_uy'], res['x_comision_traer_editor_uy'],
                res['x_comision_editor_uy'], res['x_comision_traer_editor_bmg'],
                res['x_comision_editor_bmg'], res['x_comision_bmg_propia'],
                res['x_total_bmg_terceros'], res['x_total_bmg_propio'],
                res['x_total_lad_uy'],
                order_code, line_number
            ))
            actualizados += 1
            
            if actualizados % 10 == 0:
                conn.commit()
                print(f"     ... {actualizados} procesados ...")
                time.sleep(1)
                
        except Exception as e:
            print(f"     ❌ Error en {order_code}-{line_number}: {e}")

    conn.commit()
    conn.close()
    print(f"\n--- Migración Finalizada. Se actualizaron {actualizados} líneas. ---")

if __name__ == "__main__":
    migrate()
