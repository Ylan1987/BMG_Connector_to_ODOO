# -*- coding: utf-8 -*-
import sys
import os
import json
import requests

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def investigar_sku_y_items(pap_id):
    full_pap = f"PAP{pap_id.zfill(8)}" if not pap_id.startswith('PAP') else pap_id
    print(f"--- Investigando SKU: {full_pap} ---")
    
    token = meli_api.obtener_access_token()
    seller_id = meli_api.obtener_seller_id()
    headers = {'Authorization': f'Bearer {token}'}

    # 1. Buscar TODOS los Items con ese SKU
    url_items = f"https://api.mercadolibre.com/users/{seller_id}/items/search?seller_custom_field={full_pap}"
    res_items = requests.get(url_items, headers=headers)
    item_ids = res_items.json().get('results', [])
    
    print(f"✅ Se encontraron {len(item_ids)} Items para el SKU {full_pap}: {item_ids}")

    # 2. Para cada Item, buscar órdenes
    for item_id in item_ids:
        print(f"\nBuscando órdenes para Item ID: {item_id}...")
        url_orders = f"https://api.mercadolibre.com/orders/search?seller={seller_id}&q={item_id}"
        res_orders = requests.get(url_orders, headers=headers)
        orders = res_orders.json().get('results', [])
        
        if orders:
            print(f"   🎉 ¡ENCONTRADA! {len(orders)} órdenes para {item_id}")
            for o in orders:
                print(f"      - ID Orden: {o['id']} | Comprador: {o['buyer'].get('nickname')}")
        else:
            print(f"   ❌ Sin órdenes para este Item ID.")

if __name__ == "__main__":
    investigar_sku_y_items("1013714")
