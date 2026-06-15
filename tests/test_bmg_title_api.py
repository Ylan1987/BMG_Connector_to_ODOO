# -*- coding: utf-8 -*-
from zeep import Client
from common import mapeos

def test_get_title_methods(title_id):
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print(f"--- Explorando métodos para el TitleID: {title_id} ---")
        
        # 1. Listar todos los métodos disponibles en el WSDL para que el usuario los vea
        print("\nMétodos disponibles en el Service de BMG:")
        for service in cliente_wsdl.wsdl.services.values():
            for port in service.ports.values():
                for operation in port.binding._operations.values():
                    print(f" - {operation.name}")

        # 2. Intentar los nombres más probables de métodos de consulta de títulos
        metodos_a_probar = [
            'BMGetTitle', 
            'BMTitleDetail', 
            'BMGetProduct', 
            'BMGetTitleById'
        ]
        
        for metodo_nombre in metodos_a_probar:
            if hasattr(cliente_wsdl.service, metodo_nombre):
                print(f"\nProbando método existente: {metodo_nombre}...")
                try:
                    # Intentamos la llamada (los parámetros suelen ser similares en BMG)
                    resultado = getattr(cliente_wsdl.service, metodo_nombre)(
                        TitleId=title_id,
                        FacilityUserId=mapeos.FACILITY_USER_ID,
                        Password=mapeos.PASSWORD
                    )
                    print(f"¡ÉXITO con {metodo_nombre}!")
                    print(resultado)
                except Exception as e_call:
                    print(f"Fallo al llamar a {metodo_nombre}: {e_call}")
            else:
                print(f"El método {metodo_nombre} no existe en este WSDL.")

    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    # Probamos con el ID del libro "Caminando a través del Duelo"
    test_get_title_methods("1468836")
