# -*- coding: utf-8 -*-
"""
Script de prueba para la conexión con Mercado Libre (Meli).
"""
import sys
import os

# Añadir el directorio actual al path para poder importar 'common'
sys.path.append(os.getcwd())

from common import meli_api, mapeos

def test_meli_connection():
    print("--- Probando Conexión con Mercado Libre ---")
    
    # 1. Verificar si hay token configurado
    token = meli_api.obtener_access_token()
    if not token:
        print("❌ Error: No se encontró MELI_ACCESS_TOKEN en mapeos.py o mapeos_local.py")
        return

    print(f"✅ Token encontrado (primeros 10 caracteres): {token[:10]}...")

    # 2. Probar obtener Seller ID (Verifica si el token es válido)
    print("Consultando información del vendedor (me)...")
    seller_id = meli_api.obtener_seller_id()
    
    if seller_id:
        print(f"✅ Conexión exitosa. Seller ID: {seller_id}")
    else:
        print("❌ Error: No se pudo obtener el Seller ID. Es probable que el Token haya expirado o sea inválido.")

if __name__ == "__main__":
    test_meli_connection()
