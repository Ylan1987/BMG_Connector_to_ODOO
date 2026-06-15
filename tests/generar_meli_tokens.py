# -*- coding: utf-8 -*-
"""
Script para generar el primer par de tokens (Access y Refresh) de Mercado Libre.
"""
import requests
import sys
import os

# Añadir el directorio actual al path
sys.path.append(os.getcwd())

from common import mapeos

def generar_tokens_iniciales(auth_code):
    print("--- Generando Tokens Iniciales de Mercado Libre ---")
    
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': mapeos.MELI_CLIENT_ID,
        'client_secret': mapeos.MELI_CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': 'https://imprentadiagonal.com.uy/Odoo-BMG-Nesta'
    }
    
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Tokens generados con éxito!")
            print(f"ACCESS_TOKEN: {data.get('access_token')}")
            print(f"REFRESH_TOKEN: {data.get('refresh_token')}")
            print("\nCopia estos valores en tu archivo mapeos_local.py")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Generar URL de autorización para el usuario
        # Reemplazar 'APP_ID' y 'REDIRECT_URI'
        auth_url = f"https://auth.mercadolibre.com.uy/authorization?response_type=code&client_id={mapeos.MELI_CLIENT_ID}&redirect_uri=https://localhost"
        print("Para obtener el 'auth_code', sigue estos pasos:")
        print(f"1. Abre esta URL en tu navegador: \n{auth_url}")
        print("2. Autoriza la aplicación.")
        print("3. Serás redirigido a una URL que empieza por 'https://localhost/?code=TG-XXXXX'")
        print("4. Copia el valor que aparece después de 'code=' y ejecútame así:")
        print("   python generar_meli_tokens.py TG-TU-CODE-AQUI")
    else:
        generar_tokens_iniciales(sys.argv[1])
