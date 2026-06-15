# -*- coding: utf-8 -*-
import sys
import os
import json
import requests
from datetime import datetime, timedelta

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def listar_ordenes_recientes(dias=7):
    print(f"--- Listando Órdenes de Mercado Libre (Últimos {dias} días) ---")
    
    token = meli_api.obtener_access_token()
    seller_id = meli_api.obtener_seller_id()
    
    if not token or not seller_id:
        print("❌ Error de autenticación.")
        return

    headers = {'Authorization': f'Bearer {token}'}
    
    # Calcular fecha de inicio
    fecha_inicio = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%dT00:00:00.000-00:00')
    
    # URL para buscar órdenes pagadas en el rango de fechas
    # Usamos sort=date_desc para ver las más nuevas primero
    url = f"https://api.mercadolibre.com/orders/search?seller={seller_id}&order.status=paid&order.date_created.from={fecha_inicio}&sort=date_desc"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if not results:
                print(f"❌ No se encontraron órdenes pagadas en los últimos {dias} días.")
            else:
                print(f"✅ Se encontraron {len(results)} órdenes:")
                for order in results:
                    buyer = order.get('buyer', {})
                    nick = buyer.get('nickname', 'N/A')
                    name = f"{buyer.get('first_name', '')} {buyer.get('last_name', '')}".strip() or "N/A"
                    
                    print(f"\n[ID: {order['id']}] | Fecha: {order['date_created']} | Status: {order['status']}")
                    print(f"   Comprador: {name} ({nick})")
                    
                    for item in order.get('order_items', []):
                        it = item.get('item', {})
                        print(f"   - Item: {it.get('title')[:50]}...")
                        print(f"     ID: {it.get('id')} | SKU: {it.get('seller_custom_field')}")
        else:
            print(f"❌ Error API ML: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    dias = 7
    if len(sys.argv) > 1:
        try: dias = int(sys.argv[1])
        except: pass
    listar_ordenes_recientes(dias)
