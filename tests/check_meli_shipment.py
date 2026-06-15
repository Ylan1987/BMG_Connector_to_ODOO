import json
import os
import requests
from common import meli_api, mapeos

def check_shipment_details(shipping_id):
    print(f"--- Investigando Detalle de Envío: {shipping_id} ---")
    
    token = meli_api.obtener_access_token()
    if not token:
        print("❌ No se pudo obtener Access Token.")
        return

    url = f"https://api.mercadolibre.com/shipments/{shipping_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("\n[DATOS DEL ENVÍO]")
            print(f"Status: {data.get('status')}")
            print(f"Substatus: {data.get('substatus')}")
            print(f"Service ID: {data.get('service_id')}")
            
            # Ver costos
            shipping_option = data.get('shipping_option', {})
            print(f"\n[COSTOS EN SHIPPING_OPTION]")
            print(f"Cost: {shipping_option.get('cost')} {data.get('currency_id')}")
            print(f"List Cost: {shipping_option.get('list_cost')}")
            
            # Ver si hay costo para el vendedor (lead time, etc)
            print(f"\n[COSTOS PARA VENDEDOR]")
            base_cost = data.get('base_cost')
            print(f"Base Cost: {base_cost}")
            
            print("\n" + "="*80)
            print("[RAW SHIPMENT DATA]")
            print("="*80)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("="*80)
        else:
            print(f"❌ Error API Shipments: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"🔥 Error al consultar API Shipments: {e}")

if __name__ == "__main__":
    # El shipping ID que vimos en el JSON anterior
    check_shipment_details("47109366564")
