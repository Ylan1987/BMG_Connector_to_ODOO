# -*- coding: utf-8 -*-
from zeep import Client
from common import mapeos

def check_bmg_xml_raw(order_code):
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print(f"Consultando XML RAW desde BMG para {order_code}...")
        
        resultado = cliente_wsdl.service.BMBillingByOrder(
            OrderCode=order_code, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD
        )
        
        if resultado is None:
            print("No se recibió respuesta.")
            return

        # Buscamos el PublisherId en la cabecera del pedido (Order)
        order_element = resultado.find('Order')
        if order_element is not None:
            publisher_id = order_element.find('PublisherId')
            publisher_name = order_element.find('PublisherName')
            print(f"\nDATOS DEL EDITOR EN EL XML:")
            print(f"PublisherId: {publisher_id.text if publisher_id is not None else 'No encontrado'}")
            print(f"PublisherName: {publisher_name.text if publisher_name is not None else 'No encontrado'}")
            
            # Verificamos si en las líneas hay algo diferente
            print("\nVERIFICANDO LÍNEAS:")
            for line in order_element.findall('Orderline'):
                ln = line.find('LineNumber').text
                title = line.find('Title').text
                # A veces el PublisherId viene por línea en otros métodos, pero BMBillingByOrder suele traerlo en cabecera
                print(f"Línea {ln}: {title}")
        else:
            print("No se encontró el elemento <Order>.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_bmg_xml_raw("PED00653636")
