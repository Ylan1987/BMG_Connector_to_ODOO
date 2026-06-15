
import json
import os
import requests
from common import meli_api, mapeos

def check_order_meli_full(meli_order_id):
    print(f"--- INVESTIGACIÓN COMPLETA ORDEN ML: {meli_order_id} ---")
    
    try:
        meli_data = meli_api.obtener_detalle_orden_ml(meli_order_id)
        
        if not meli_data:
            print("❌ No se pudo obtener información de la orden.")
            return

        print("\n[RESUMEN CALCULADO POR EL SCRIPT]")
        print(f"Total Pagado: {meli_data['total_paid']} UYU")
        print(f"Costo Envío: {meli_data['shipping_cost']}")
        print(f"Precios por SKU: {meli_data['items_prices']}")

        print("\n" + "="*80)
        print("[RAW DATA - JSON COMPLETO DE MERCADOLIBRE]")
        print("="*80)
        print(json.dumps(meli_data['raw_data'], indent=2, ensure_ascii=False))
        print("="*80)
        
    except Exception as e:
        print(f"🔥 Error al consultar API de MercadoLibre: {e}")

if __name__ == "__main__":
    check_order_meli_full("2000016528717690")
