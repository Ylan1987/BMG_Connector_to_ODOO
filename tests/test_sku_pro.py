# -*- coding: utf-8 -*-
import sys
import os
import json
import requests

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def buscar_orden_por_sku_pro(pap_id):
    # Asegurar prefijo PAP0XXXXXXXX
    full_pap = f"PAP{pap_id.zfill(8)}" if not pap_id.startswith('PAP') else pap_id
    print(f"--- Iniciando búsqueda PRO para SKU: {full_pap} ---")
    
    token = meli_api.obtener_access_token()
    seller_id = meli_api.obtener_seller_id()
    
    if not token or not seller_id:
        print("❌ Error de autenticación.")
        return

    headers = {'Authorization': f'Bearer {token}'}

    # PASO 1: Buscar el Item ID asociado al SKU (seller_custom_field)
    print(f"Paso 1: Buscando Item ID para el SKU {full_pap}...")
    url_item = f"https://api.mercadolibre.com/users/{seller_id}/items/search?seller_custom_field={full_pap}"
    
    try:
        res_item = requests.get(url_item, headers=headers, timeout=10)
        if res_item.status_code == 200:
            results_item = res_item.json().get('results', [])
            if not results_item:
                print(f"❌ No se encontró ningún anuncio (Item) con el SKU {full_pap} en tu cuenta.")
                return
            
            item_id = results_item[0]
            print(f"✅ Item ID encontrado: {item_id}")
            
            # PASO 2: Buscar órdenes que contengan ese Item ID
            print(f"Paso 2: Buscando órdenes para el Item ID {item_id}...")
            url_order = f"https://api.mercadolibre.com/orders/search?seller={seller_id}&q={item_id}"
            
            res_order = requests.get(url_order, headers=headers, timeout=10)
            if res_order.status_code == 200:
                results_order = res_order.json().get('results', [])
                if not results_order:
                    print(f"❌ No hay órdenes recientes para el Item ID {item_id}.")
                else:
                    print(f"✅ Se encontraron {len(results_order)} órdenes:")
                    for order in results_order:
                        print(f"\n   -> ID Orden: {order['id']}")
                        print(f"      Comprador: {order['buyer'].get('first_name', 'N/A')} {order['buyer'].get('last_name', 'N/A')} ({order['buyer'].get('nickname', 'N/A')})")
                        print(f"      Fecha: {order['date_created']}")
                        print(f"      Estado: {order['status']}")
            else:
                print(f"❌ Error al buscar órdenes: {res_order.status_code}")
        else:
            print(f"❌ Error al buscar Item: {res_item.status_code} - {res_item.text}")
            
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_sku_pro.py PAP_ID")
    else:
        buscar_orden_por_sku_pro(sys.argv[1])
