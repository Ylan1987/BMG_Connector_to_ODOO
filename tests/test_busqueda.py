# -*- coding: utf-8 -*-
import sys
import os
import json

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common.meli_api import buscar_orden_por_isbn_y_nombre

def test_busqueda(pap_id, nombre):
    # Asegurar prefijo PAP
    full_pap = f"PAP{pap_id.zfill(8)}" if not pap_id.startswith('PAP') else pap_id
    print(f"Buscando en ML: PAP/SKU={full_pap}, Nombre='{nombre}'...")
    resultado = buscar_orden_por_isbn_y_nombre(full_pap, nombre)
    
    if resultado:
        if 'multiple_matches' in resultado:
            print("\n⚠️ Se encontraron MÚLTIPLES coincidencias.")
        else:
            print("\n✅ COINCIDENCIA ÚNICA ENCONTRADA:")
            print(f"   - ID Orden: {resultado['raw_data']['id']}")
            print(f"   - Comprador: {resultado['raw_data']['buyer']['first_name']} {resultado['raw_data']['buyer']['last_name']}")
            print(f"   - Título: {resultado['raw_data']['order_items'][0]['item']['title']}")
            print(f"   - Precios: {resultado['items_prices']}")
    else:
        print("\n❌ No se encontró ninguna coincidencia en Mercado Libre.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python test_busqueda.py ISBN NOMBRE")
    else:
        # Unir el resto de argumentos como el nombre (por si tiene espacios)
        isbn_arg = sys.argv[1]
        nombre_arg = " ".join(sys.argv[2:])
        test_busqueda(isbn_arg, nombre_arg)
