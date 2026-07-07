import sys
import os
import sqlite3
import datetime

# Asegurar que el entorno reconozca las importaciones locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import odoo_conn, mapeos

def safe_float_conversion(val):
    if val is None or val == '':
        return 0.0
    try:
        # Reemplazar coma por punto por si acaso
        val = str(val).replace(',', '.')
        return float(val)
    except:
        return 0.0

def corregir_precios():
    print("--- INICIANDO CORRECCIÓN RETROACTIVA DE PRECIOS ---")
    
    # 1. Conectar a Odoo
    odoo_api = odoo_conn.conectar_odoo()
    if not odoo_api:
        print("❌ Error: No se pudo conectar a Odoo.")
        return
        
    sale_line_model = odoo_api.env['sale.order.line']
    sale_order_model = odoo_api.env['sale.order']

    # 2. Conectar a la base de datos específica (trabajos (9).db)
    db_path = r'C:\Users\ylana\Downloads\trabajos (9).db'
    if not os.path.exists(db_path):
        print(f"❌ Error: No se encontró la base de datos en {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar los pedidos que cumplen la regla
    query = """
        SELECT *
        FROM trabajos 
        WHERE publisher_facility != 'LAD'
        AND business_unit LIKE '%eDistribuc%'
        AND order_type NOT LIKE '%eDistrib%'
        AND odoo_sale_order_line_id IS NOT NULL
    """
    cursor.execute(query)
    trabajos = cursor.fetchall()
    
    print(f"✅ Se encontraron {len(trabajos)} líneas de trabajo candidatas para aplicar descuento.")
    
    lineas_actualizadas = 0
    errores = 0
    ordenes_notificadas = set()
    
    for row in trabajos:
        line_id = row['odoo_sale_order_line_id']
        order_code = row['order_code']
        line_number = row['line_number']
        
        # Calcular el precio base original
        moneda_code_actual = row['unit_currency'].upper() if row['unit_currency'] else mapeos.CURRENCY_UYU
        # Forzar USD porque publisher != LAD
        if not (row['order_type'] == mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1) and row['publisher_facility'] != mapeos.BMG_PUBLISHER_FACILITY_LAD:
            moneda_code_actual = mapeos.CURRENCY_USD
            
        precio_base = safe_float_conversion(row['unit_price_invoice'] if moneda_code_actual == mapeos.CURRENCY_USD else row['unit_price'])
        precio_base += safe_float_conversion(row['unit_price_adjustment'])
        
        # Aplicar el descuento de 1.5
        precio_correcto = max(0.0, precio_base - 1.5)
        
        try:
            # Buscar la línea en Odoo
            sol = sale_line_model.browse(line_id)
            if not sol.exists():
                print(f"⚠️ [IGNORADO] Línea Odoo ID {line_id} (Pedido BMG {order_code}) ya no existe en Odoo.")
                continue
                
            precio_actual_odoo = sol.price_unit
            order_id = sol.order_id.id
            
            # Si el precio actual en Odoo es diferente al precio corregido
            if abs(precio_actual_odoo - precio_correcto) > 0.01:
                # Ojo: si el precio en Odoo ya es el original y no se le restó, lo restamos.
                # Pero ¿qué pasa si en Odoo tiene OTRO precio por otra regla (ej. ML)?
                # Verifiquemos si el precio actual se parece al precio_base
                if abs(precio_actual_odoo - precio_base) < 0.01 or abs(precio_actual_odoo - precio_correcto) > 0.01:
                    print(f"  -> 🔄 Actualizando Odoo Line ID {line_id} (BMG: {order_code}-{line_number}): USD {precio_actual_odoo} -> USD {precio_correcto}")
                    sol.write({'price_unit': precio_correcto})
                    lineas_actualizadas += 1
                    
                    # Dejar nota en el chatter de la orden (solo 1 vez por orden)
                    if order_id not in ordenes_notificadas:
                        msg = "<p><i>⚠️ <b>Precio corregido retroactivamente</b>: Se aplicó el descuento de USD 1.5 a los artículos de este pedido por cumplir la regla de Editor Extranjero + BU eDistribución.</i></p>"
                        try:
                            # odoo_api.execute('sale.order', 'message_post', [order_id], {'body': msg, 'message_type': 'comment', 'subtype_xmlid': 'mail.mt_note'})
                            sale_order_model.browse(order_id).message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
                            ordenes_notificadas.add(order_id)
                        except Exception as em:
                            print(f"     ⚠️ No se pudo dejar nota en la orden {order_id}: {em}")
            else:
                # Ya tiene el precio correcto
                pass
                
        except Exception as e:
            print(f"❌ Error al procesar Odoo Line ID {line_id} (BMG {order_code}): {e}")
            errores += 1

    conn.close()
    print("\n--- RESUMEN ---")
    print(f"Líneas procesadas (con descuento teórico): {len(trabajos)}")
    print(f"Líneas actualizadas en Odoo: {lineas_actualizadas}")
    print(f"Órdenes anotadas en Chatter: {len(ordenes_notificadas)}")
    print(f"Errores: {errores}")
    print("-------------------------------------------------")

if __name__ == '__main__':
    corregir_precios()
