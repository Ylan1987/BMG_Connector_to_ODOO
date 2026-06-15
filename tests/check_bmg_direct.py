# -*- coding: utf-8 -*-
from zeep import Client
from common import mapeos
import json

def check_bmg_order(order_code):
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print(f"Conectado a BMG. Consultando {order_code}...")
        
        resultado_detalle = cliente_wsdl.service.BMBillingByOrder(
            OrderCode=order_code, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD
        )
        
        if resultado_detalle is None:
            print("No se recibió respuesta para el pedido.")
            return

        order_element = resultado_detalle.find('Order')
        if order_element is None:
            print("No se encontró el elemento <Order> en la respuesta.")
            # Intento imprimir la respuesta completa para debug
            print(resultado_detalle)
            return

        def get_text(element, tag):
            if element is None: return 'N/A'
            child = element.find(tag)
            return child.text.strip() if child is not None and child.text else 'N/A'

        print("\n--- Cabecera del Pedido ---")
        print(f"OrderCode: {get_text(order_element, 'OrderCode')}")
        print(f"PrintingFacilityNumber: {get_text(order_element, 'PrintingFacilityNumber')}")
        print(f"PublisherFacility: {get_text(order_element, 'PublisherFacility')}")
        print(f"OrderType: {get_text(order_element, 'OrderType')}")
        print(f"OrderDate: {get_text(order_element, 'OrderDate')}")
        print(f"PrintingFacility: {get_text(order_element, 'PrintingFacility')}")

        lineas = order_element.findall('Orderline')
        print(f"\n--- Líneas ({len(lineas)}) ---")
        for line in lineas:
            print(f"Línea: {get_text(line, 'LineNumber')} | Status: {get_text(line, 'LineStatus')} (ID: {get_text(line, 'LineStatusId')}) | Title: {get_text(line, 'Title')}")

        # Lógica de script_01 para estado_odoo_inicial
        order_type_xml = get_text(order_element, 'OrderType')
        printing_facility_number_xml = get_text(order_element, 'PrintingFacilityNumber')
        publisher_facility_xml = get_text(order_element, 'PublisherFacility')
        
        es_edist = mapeos.BMG_ORDER_TYPE_EDIST in order_type_xml
        es_pod = not es_edist
        
        # FACILITY_ID en mapeos es '128'
        match_facility = (printing_facility_number_xml == mapeos.FACILITY_ID)
        match_lad = (publisher_facility_xml == mapeos.BMG_PUBLISHER_FACILITY_LAD)
        
        print("\n--- Evaluación de Filtros ---")
        print(f"Es eDist: {es_edist}")
        print(f"Es POD: {es_pod}")
        print(f"Printing Facility match ({mapeos.FACILITY_ID}): {match_facility}")
        print(f"Publisher Facility es LAD: {match_lad}")
        
        estado_odoo_inicial = "NO_APLICA"
        if (es_edist and match_facility) or \
           (es_pod and (match_facility or match_lad)):
            estado_odoo_inicial = "LISTO_PARA_SINCRONIZAR"
            
        print(f"RESULTADO: El estado inicial sería: {estado_odoo_inicial}")

    except Exception as e:
        print(f"Error consultando BMG: {e}")

if __name__ == "__main__":
    check_bmg_order("PED00653636")
    # También pruebo sin el prefijo por si acaso
    # check_bmg_order("653636")
