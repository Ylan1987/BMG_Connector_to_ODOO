# -*- coding: utf-8 -*-
import sqlite3
import requests
import re
import time
import os
import sys

# Asegurar que podemos importar desde el directorio actual
sys.path.append(os.getcwd())

from common import mapeos, db_conn, odoo_conn

def detect_origin(title_id):
    pub_id_test = "108907" 
    title_id_num = "".join(filter(str.isdigit, str(title_id)))
    for country in ["ES", "UY"]:
        url = f"https://canal.bibliomanager.com/titulos/{country}/143/{pub_id_test}/{title_id_num}/{title_id_num}_IMAGEN_TAPA_G_002.jpg"
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200: return country
        except: continue
    return "ES"

def safe_float(value):
    if not value: return 0.0
    try:
        return float(str(value).replace(',', ''))
    except: return 0.0

def calculate_finance(row):
    pvp = safe_float(row['unit_price'])
    p_canal = safe_float(row['unit_price_channel'])
    costo_imp = safe_float(row['unit_price_invoice'])
    origen = detect_origin(row['title_id'])
    es_uy = (origen == "UY")
    
    com_lib = pvp * 0.05
    com_traer_ed = pvp * 0.05
    com_editor = pvp * 0.25
    
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
    
    if es_uy:
        res['x_total_lad_uy'] = costo_imp + com_lib + com_traer_ed + com_editor
        res['x_total_bmg_terceros'] = 0
    else:
        res['x_total_lad_uy'] = costo_imp + com_lib
        res['x_total_bmg_terceros'] = com_traer_ed + com_editor
        
    res['x_comision_bmg_propia'] = p_canal - (res['x_total_lad_uy'] + res['x_total_bmg_terceros'])
    res['x_total_bmg_propio'] = res['x_comision_bmg_propia']
    return res

def migrate_odoo():
    print("--- Iniciando Sincronización Masiva Local -> Odoo ---")
    
    # 1. Conectar a Odoo
    print("Conectando a Odoo...")
    odoo = odoo_conn.conectar_odoo()
    if not odoo:
        print("Fallo de conexión a Odoo.")
        return
    sol_model = odoo.env['sale.order.line']

    # 2. Conectar a DB Local
    conn = db_conn.conectar_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscamos líneas que ya estén en Odoo pero no tengan el cálculo en la DB local aún
    # (O que queramos forzar actualización)
    cursor.execute(f"SELECT * FROM trabajos WHERE odoo_sale_order_line_id IS NOT NULL AND order_type LIKE '%{mapeos.BMG_ORDER_TYPE_EDIST}%'")
    rows = cursor.fetchall()
    
    print(f"Se encontraron {len(rows)} líneas en Odoo para actualizar.")
    
    count = 0
    for row in rows:
        order_code = row['order_code']
        sol_id = row['odoo_sale_order_line_id']
        
        print(f"  -> {order_code}: Actualizando SOL {sol_id}...")
        
        try:
            # Calcular
            finance = calculate_finance(row)
            
            # Actualizar en Odoo
            sol_model.write([sol_id], finance)
            
            # Actualizar en DB Local (para que queden sincronizados)
            cursor.execute("""
                UPDATE trabajos SET
                    x_origen_pais = ?, x_precio_canal = ?, x_costo_impresion_uy = ?,
                    x_comision_traer_libreria_uy = ?, x_comision_traer_editor_uy = ?,
                    x_comision_editor_uy = ?, x_comision_traer_editor_bmg = ?,
                    x_comision_editor_bmg = ?, x_comision_bmg_propia = ?,
                    x_total_bmg_terceros = ?, x_total_bmg_propio = ?, x_total_lad_uy = ?
                WHERE odoo_sale_order_line_id = ?
            """, (
                finance['x_origen_pais'], finance['x_precio_canal'], finance['x_costo_impresion_uy'],
                finance['x_comision_traer_libreria_uy'], finance['x_comision_traer_editor_uy'],
                finance['x_comision_editor_uy'], finance['x_comision_traer_editor_bmg'],
                finance['x_comision_editor_bmg'], finance['x_comision_bmg_propia'],
                finance['x_total_bmg_terceros'], finance['x_total_bmg_propio'],
                finance['x_total_lad_uy'], sol_id
            ))
            
            count += 1
            if count % 5 == 0:
                conn.commit()
                print(f"     ... {count} actualizados ...")
                time.sleep(0.5)

        except Exception as e:
            print(f"     ❌ Error actualizando SOL {sol_id}: {e}")

    conn.commit()
    conn.close()
    print(f"--- Sincronización Finalizada. {count} líneas actualizadas en Odoo y DB local. ---")

if __name__ == "__main__":
    migrate_odoo()
