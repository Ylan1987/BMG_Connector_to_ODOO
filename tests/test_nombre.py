# -*- coding: utf-8 -*-
import sys
import os
import json
import requests

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def buscar_por_nombre(nombre):
    print(f"Buscando en ML órdenes para el nombre: '{nombre}'...")
    
    token = meli_api.obtener_access_token()
    seller_id = meli_api.obtener_seller_id()
    
    if not token or not seller_id:
        print("❌ Error de autenticación.")
        return

    # Buscar órdenes por el nombre del comprador (usando el parámetro 'q')
    url = f"https://api.mercadolibre.com/orders/search?seller={seller_id}&q={nombre}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if not results:
                print(f"❌ No se encontraron órdenes para el nombre '{nombre}'.")
            else:
                print(f"✅ Se encontraron {len(results)} órdenes:")
                for order in results:
                    buyer = order.get('buyer', {})
                    fname = buyer.get('first_name', 'N/A')
                    lname = buyer.get('last_name', 'N/A')
                    nick = buyer.get('nickname', 'N/A')
                    print(f"\n--- Orden ID: {order['id']} ---")
                    print(f"   Comprador: {fname} {lname} ({nick})")
                    print(f"   Fecha: {order['date_created']}")
                    for item in order.get('order_items', []):
                        item_info = item.get('item', {})
                        print(f"   Item: {item_info.get('title', 'N/A')}")
                        print(f"   SKU (Custom Field): {item_info.get('seller_custom_field')}")
        else:
            print(f"❌ Error API ML: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_nombre.py NOMBRE")
    else:
        nombre_arg = " ".join(sys.argv[1:])
        buscar_por_nombre(nombre_arg)
