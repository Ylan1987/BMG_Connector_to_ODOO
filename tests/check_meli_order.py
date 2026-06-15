import json
import os
from common import meli_api, mapeos

def check_order_meli(meli_order_id):
    print(f"--- Investigando Orden MercadoLibre: {meli_order_id} ---")
    
    # Intentar obtener los datos de la orden
    try:
        # La función correcta es obtener_detalle_orden_ml
        meli_data = meli_api.obtener_detalle_orden_ml(meli_order_id)
        if not meli_data:
            print(f"❌ No se pudo obtener información para la orden {meli_order_id}")
            return

        print(f"\n[DATOS GENERALES]")
        print(f"Total Paid: {meli_data.get('total_paid')} UYU")
        print(f"Shipping Cost: {meli_data.get('shipping_cost')}")
        
        # Revisar ítems y sus precios
        print(f"\n[ITEMS]")
        items_prices = meli_data.get('items_prices', {})
        for ref, price in items_prices.items():
            print(f"- SKU/Ref: {ref} -> Precio: {price}")

        # Ver datos crudos de pagos si es necesario
        raw_data = meli_data.get('raw_data', {})
        payments = raw_data.get('payments', [])
        if payments:
            print(f"\n[PAGOS ENCONTRADOS]")
            for p in payments:
                print(f"- Pago ID: {p.get('id')} | Status: {p.get('status')} | Amount: {p.get('total_paid_amount')} | Shipping: {p.get('shipping_cost')}")
        
    except Exception as e:
        print(f"🔥 Error al consultar API de MercadoLibre: {e}")

if __name__ == "__main__":
    check_order_meli("2000016526256058")
