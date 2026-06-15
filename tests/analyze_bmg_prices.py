# -*- coding: utf-8 -*-
from zeep import Client
from common import mapeos
import xml.etree.ElementTree as ET

def analyze_bmg_pricing(order_code):
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print(f"Consultando XML completo para {order_code}...")
        
        resultado_xml = cliente_wsdl.service.BMBillingByOrder(
            OrderCode=order_code, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD
        )
        
        if resultado_xml is None:
            print("No se recibió respuesta.")
            return

        # El resultado suele ser un objeto, pero lo convertimos a string XML si es posible
        # o lo recorremos para encontrar etiquetas de precio.
        
        # Intentamos encontrar todas las etiquetas que contengan 'Price', 'Cost' o 'Currency'
        print("\n--- Análisis de Etiquetas de Precio y Costo ---")
        
        def recurse_elements(element, depth=0):
            tag = element.tag
            text = element.text.strip() if element.text else ""
            
            # Buscamos palabras clave en el tag
            keywords = ['Price', 'Cost', 'Currency', 'Adjustment', 'Exchange', 'Amount', 'Total']
            if any(k.lower() in tag.lower() for k in keywords):
                print(f"{'  ' * depth}{tag}: {text}")
            
            for child in element:
                recurse_elements(child, depth + 1)

        recurse_elements(resultado_xml)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_bmg_pricing("PED00653636")
