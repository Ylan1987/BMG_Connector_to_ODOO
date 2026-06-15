# -*- coding: utf-8 -*-
import sys
import os
import json

# Añadir el directorio raíz al path para importar common
sys.path.append(os.getcwd())

from common.meli_api import obtener_detalle_orden_ml

def test_funcion_posta(order_id):
    print(f"Llamando a obtener_detalle_orden_ml('{order_id}')...")
    resultado = obtener_detalle_orden_ml(order_id)
    
    if resultado:
        # Imprimimos el resultado formateado para ver qué trae la función real
        print("\n--- RESULTADO DE LA FUNCIÓN ---")
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
    else:
        print("\n❌ La función devolvió None. Revisa los logs o el ID.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_real.py ID_ORDEN")
    else:
        test_funcion_posta(sys.argv[1])
