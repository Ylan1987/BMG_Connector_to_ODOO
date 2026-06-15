# -*- coding: utf-8 -*-
import sys
import os
import json
import requests

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def buscar_solo_por_pap(pap_id):
    # Asegurar prefijo PAP0XXXXXXXX (11 caracteres)
    full_pap = f"PAP{pap_id.zfill(8)}" if not pap_id.startswith('PAP') else pap_id
    print(f"Buscando en ML SOLO por SKU/Query: {full_pap}...")
    
    token = meli_api.obtener_access_token()
    seller_id = meli_api.obtener_seller_id()
    
    if not token or not seller_id:
        print("❌ Error de autenticación.")
        return

    # Buscar órdenes que contengan el PAP
    url = f"https://api.mercadolibre.com/orders/search?seller={seller_id}&q={full_pap}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if not results:
                print(f"❌ No se encontraron órdenes para el término '{full_pap}'.")
            else:
                print(f"✅ Se encontraron {len(results)} órdenes:")
                for order in results:
                    print(f"\n--- Orden ID: {order['id']} ---")
                    print(f"   Comprador: {order['buyer']['first_name']} {order['buyer']['last_name']}")
                    print(f"   Fecha: {order['date_created']}")
                    for item in order['order_items']:
                        print(f"   Item: {item['item']['title']}")
                        print(f"   SKU (Custom Field): {item['item'].get('seller_custom_field')}")
        else:
            print(f"❌ Error API ML: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_solo_pap.py PAP_ID")
    else:
        buscar_solo_por_pap(sys.argv[1])
