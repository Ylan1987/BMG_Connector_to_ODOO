# -*- coding: utf-8 -*-
from zeep import Client
from common import mapeos

def deep_check_bmg_lines(order_code):
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print(f"Consultando XML profundo para {order_code}...")
        
        resultado = cliente_wsdl.service.BMBillingByOrder(
            OrderCode=order_code, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD
        )
        
        if resultado is None:
            print("No se recibió respuesta.")
            return

        order_element = resultado.find('Order')
        if order_element is not None:
            print(f"\n--- CABECERA DEL PEDIDO ---")
            print(f"Order PublisherId: {order_element.findtext('PublisherId')}")
            print(f"Order PublisherName: {order_element.findtext('PublisherName')}")

            print(f"\n--- DETALLE DE LÍNEAS (BUSCANDO EDITORES ESPECÍFICOS) ---")
            for line in order_element.findall('Orderline'):
                ln = line.findtext('LineNumber')
                title = line.findtext('Title')
                isbn = line.findtext('ISBN')
                
                # Buscamos cualquier campo que hable de editor, publisher o autor en la línea
                p_id = line.findtext('PublisherId')
                p_name = line.findtext('PublisherName')
                author = line.findtext('Author')
                
                print(f"\n[Línea {ln}]")
                print(f"  Título: {title}")
                print(f"  ISBN: {isbn}")
                print(f"  PublisherId en línea: {p_id if p_id else '(No existe en el tag de línea)'}")
                print(f"  PublisherName en línea: {p_name if p_name else '(No existe en el tag de línea)'}")
                print(f"  Author: {author}")
                
                # Si no están los tags estándar, listamos TODOS los tags de la línea para no perder nada
                if not p_id:
                    print("  Tags disponibles en esta línea:")
                    tags = [child.tag for child in line]
                    print(f"  {', '.join(tags)}")

        else:
            print("No se encontró el elemento <Order>.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_check_bmg_lines("PED00653636")
