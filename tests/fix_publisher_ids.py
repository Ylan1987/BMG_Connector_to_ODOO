# -*- coding: utf-8 -*-
"""
Script temporal para corregir el campo 'publisher_id' en la base de datos local.

Este script lee todos los pedidos de la base de datos local, consulta la API de BMG
para cada uno, extrae todos los PublisherIDs de cada línea de pedido, y actualiza
el campo 'publisher_id' con una cadena separada por comas de todos los IDs encontrados.
"""

import sqlite3
from lxml import etree
from zeep import Client
from datetime import datetime

# Importar módulos comunes de la V2.0
from common import db_conn, mapeos

def get_bmg_client():
    """Configura y devuelve un cliente SOAP para la API de BMG, usando la misma lógica que script_01."""
    try:
        client = Client(mapeos.WSDL_URL)
        print("✅ Cliente SOAP para BMG API creado con éxito.")
        return client
    except Exception as e:
        print(f"❌ Error al crear el cliente SOAP de BMG: {e}")
        return None

def get_order_details_from_bmg(client, order_code):
    """Llama a BMBillingByOrder y devuelve el elemento <Order> de la respuesta."""
    try:
        print(f"  - Consultando BMG para el pedido: {order_code}...")
        response_zeep = client.service.BMBillingByOrder(
            OrderCode=order_code,
            FacilityUserId=mapeos.FACILITY_USER_ID,
            Password=mapeos.PASSWORD
        )
        
        if response_zeep is None:
            print(f"    - La API de BMG no devolvió datos para el pedido {order_code}.")
            return None

        # La respuesta de Zeep ya es un objeto navegable. Buscamos el nodo 'Order'.
        order_element = response_zeep.find('Order')
        if order_element is None:
            print(f"    - No se encontró el elemento <Order> en la respuesta para {order_code}.")
            return None

        return order_element
    except Exception as e:
        print(f"    ❌ Error al llamar a BMBillingByOrder para {order_code}: {e}")
        return None

def parse_and_update_db(order_code, order_element):
    """Parsea el elemento <Order>, extrae los PublisherIDs y actualiza la DB para todas las líneas."""
    if order_element is None:
        return

    try:
        # Extraer todos los PublisherId del elemento Order
        publisher_id_elements = order_element.findall('PublisherId')
        publisher_ids = [pid.text.strip() for pid in publisher_id_elements if pid.text]
        
        if not publisher_ids:
            print(f"  - No se encontraron PublisherIDs en la respuesta de BMG para el pedido {order_code}.")
            return

        new_publisher_id_str = ','.join(publisher_ids)
        print(f"  - IDs de Publisher encontrados para {order_code}: '{new_publisher_id_str}'")

        # Actualizar todas las líneas de este pedido en la DB
        conn = db_conn.conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trabajos SET publisher_id = ? WHERE order_code = ?",
            (new_publisher_id_str, order_code)
        )
        updated_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"  - ✅ DB actualizada para {updated_rows} línea(s) del pedido {order_code}.")

    except Exception as e:
        print(f"    ❌ Error al parsear o actualizar la DB para {order_code}: {e}")

def run():
    """Función principal del script."""
    print("--- Iniciando Script de Corrección de Publisher IDs ---")
    
    # 1. Conectar a la DB y obtener todos los pedidos
    try:
        conn = db_conn.conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT order_code FROM trabajos")
        pedidos = [row['order_code'] for row in cursor.fetchall()]
        print(f"Se encontraron {len(pedidos)} pedidos únicos para verificar.")
    except Exception as e:
        print(f"❌ Error fatal: No se pudo leer la lista de pedidos de la base de datos. {e}")
        return
    finally:
        if conn:
            conn.close()

    # 2. Conectar a la API de BMG
    bmg_client = get_bmg_client()
    if not bmg_client:
        print("❌ Error fatal: No se pudo conectar a la API de BMG. Abortando.")
        return

    # 3. Procesar cada pedido
    for i, order_code in enumerate(pedidos, 1):
        print(f"\n--- ({i}/{len(pedidos)}) Procesando Pedido: {order_code} ---")
        
        # Obtener detalles de BMG
        order_element = get_order_details_from_bmg(bmg_client, order_code)
        if order_element is None:
            continue
            
        # Parsear los IDs y actualizar la DB
        parse_and_update_db(order_code, order_element)

    print("\n--- Proceso de corrección finalizado. ---")

if __name__ == "__main__":
    run()