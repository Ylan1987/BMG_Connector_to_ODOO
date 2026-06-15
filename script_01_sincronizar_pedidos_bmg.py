# -*- coding: utf-8 -*-
"""
Script 1: Sincronizador de Pedidos desde BMG a la Base de Datos Local.

- Se conecta a la API de BMG para obtener los pedidos de las últimas 24 horas.
- Compara con la base de datos local y procesa solo los pedidos NUEVOS.
- Para cada pedido nuevo, obtiene los detalles y los guarda en la DB.
"""

import json
import sqlite3
import requests
from datetime import datetime, timedelta
from zeep import Client

# Importar módulos comunes de la V2.0
from common import mapeos, db_conn

def detectar_origen_por_url(title_id):
    """
    Detecta si un libro es de Uruguay (UY) o España (ES) verificando la URL de su portada.
    """
    # El Publisher ID de Deja Vu suele ser 108907 en el sistema
    # Si tenemos varios, probamos el más común o el que venga en el pedido.
    pub_id_test = "108907" 
    title_id_num = "".join(filter(str.isdigit, str(title_id)))
    
    # Intentamos ES primero, luego UY
    for country in ["ES", "UY"]:
        url = f"https://canal.bibliomanager.com/titulos/{country}/143/{pub_id_test}/{title_id_num}/{title_id_num}_IMAGEN_TAPA_G_002.jpg"
        try:
            # Petición HEAD rápida para verificar existencia
            r = requests.head(url, timeout=3)
            if r.status_code == 200:
                return country, url
        except:
            continue
    return "ES", "" # Por defecto ES si no se encuentra o hay error

def calcular_matematica_pura(datos):
    """
    Realiza los cálculos de comisiones basados en el origen y los precios.
    """
    pvp = float(datos.get('unit_price') or 0)
    p_canal = float(datos.get('unit_price_channel') or 0)
    costo_imp = float(datos.get('unit_price_invoice') or 0)
    
    origen, url = detectar_origen_por_url(datos.get('title_id'))
    es_uy = (origen == "UY")
    
    # Comisiones estándar
    com_lib = pvp * 0.05
    com_traer_ed = pvp * 0.05
    com_editor = pvp * 0.25
    
    # Distribución según origen
    res = {
        'x_origen_pais': origen,
        'x_precio_canal': p_canal,
        'x_costo_impresion_uy': costo_imp,
        'x_comision_traer_libreria_uy': com_lib,
        'x_comision_traer_editor_uy': com_traer_ed if es_uy else 0,
        'x_comision_editor_uy': com_editor if es_uy else 0,
        'x_comision_traer_editor_bmg': 0 if es_uy else com_traer_ed,
        'x_comision_editor_bmg': 0 if es_uy else com_editor,
    }
    
    # Totales
    if es_uy:
        res['x_total_lad_uy'] = costo_imp + com_lib + com_traer_ed + com_editor
        res['x_total_bmg_terceros'] = 0
    else:
        res['x_total_lad_uy'] = costo_imp + com_lib
        res['x_total_bmg_terceros'] = com_traer_ed + com_editor
        
    # El remanente es BMG Propio
    res['x_comision_bmg_propia'] = p_canal - (res['x_total_lad_uy'] + res['x_total_bmg_terceros'])
    res['x_total_bmg_propio'] = res['x_comision_bmg_propia']
    
    return res

def sincronizar_linea_con_db(order_element, line_element):
    """
    Parsea los datos de un <Orderline> y su <Order> contenedor y los guarda en la DB.
    """
    def get_text(element, tag):
        if element is None: return ''
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ''

    def get_all_text_comma_separated(element, tag):
        if element is None: return ''
        children = element.findall(tag)
        if not children: return ''
        return ','.join([child.text.strip() for child in children if child.text])

    attributes = line_element.find('Attributes')
    usd_exchange_rate = get_text(line_element, 'USDExchange')
    
    datos = {
        "order_code": get_text(line_element, 'OrderCode'), "line_number": get_text(line_element, 'LineNumber'),
        "fecha_actualizacion": datetime.now().isoformat(), "publisher_facility": get_text(order_element, 'PublisherFacility'),
        "publisher_id": get_all_text_comma_separated(order_element, 'PublisherId'), "title_id": get_text(line_element, 'TitleId'),
        "order_date": get_text(order_element, 'OrderDate'), "client_reference": get_text(order_element, 'ClientReference'),
        "business_unit": get_text(order_element, 'BusinessUnit'), "publisher_name": get_text(order_element, 'PublisherName'),
        "order_type": get_text(order_element, 'OrderType'), "run": get_text(line_element, 'Run'),
        "line_status": get_text(line_element, 'LineStatus'),
        "line_status_id": get_text(line_element, 'LineStatusId'),
        # "odoo_sale_order_name": get_text(order_element, 'ClientReference'), # Eliminado por solicitud del usuario
        "code": get_text(line_element, 'Code'),
        "title": get_text(line_element, 'Title'), "line_status_date": get_text(line_element, 'LineStatusDate'),
        "delivery_date": get_text(line_element, 'DeliveryDate'), "quantity_requested": get_text(line_element, 'QuantityRequested'),
        "total_pages": get_text(line_element, 'TotalPages'), "height": get_text(line_element, 'Height'),
        "width": get_text(line_element, 'Width'), "bleed": get_text(line_element, 'Bleed'),
        "spine": get_text(line_element, 'Spine'), "weight": get_text(line_element, 'Weight'),
        "bw_paper_type": get_text(attributes, 'BWPaperType'), "color_paper_type": get_text(attributes, 'ColorPaperType'),
        "laminate": get_text(attributes, 'Laminate'), "binding": get_text(attributes, 'Binding'),
        "publisher_observations": get_text(line_element, 'PublisherObservations'),
        "cover_printing_type": get_text(attributes, 'CoverPrintingType'),
        "color_insert": get_text(attributes, 'ColorInsert'), "color_pages": get_text(attributes, 'ColorPages'),
        "flaps_code": get_text(attributes, 'Flaps'), "flaps_width": get_text(attributes, 'FlapsWidth'),
        "unit_price": get_text(line_element, 'UnitPrice'),
        "unit_price_adjustment": get_text(line_element, 'UnitPriceAdjustment'),
        "unit_currency": get_text(line_element, 'UnitCurrency'),
        "unit_currency_exchange": get_text(line_element, 'UnitCurrencyExchange'),
        "unit_price_invoice": get_text(line_element, 'UnitPriceInvoice'),
        "unit_price_channel": get_text(line_element, 'UnitPriceChannel'),
        "additional_services": get_text(line_element, 'AdditionalServices'),
        "usd_exchange": usd_exchange_rate if usd_exchange_rate else get_text(order_element, 'USDExchange'),
        "shipping_cost_order": get_text(order_element, 'ShippingCost'),
        "shipping_cost_order_adjustment": get_text(order_element, 'ShippingCostAdjustment'),
        "shipping_cost_currency": get_text(order_element, 'ShippingCostCurrency'),
        "channel": get_text(order_element, 'Channel'),
        "billing_number": get_text(order_element, 'BillingNumber'),
        "bw_pages": get_text(attributes, 'BWPages'),
        "sealing": get_text(attributes, 'Sealing'),
        "printing_facility": get_text(order_element, 'PrintingFacility')
    }

    shipping_instructions = []
    for instruction in order_element.findall('ShippingInstruction'):
        dest_info = {
            "InstructionLine": get_text(instruction, 'InstructionLine'), "Tipo_Envio": get_text(instruction, 'ShippingType'),
            "Operador": get_text(instruction, 'Operator'), "Empresa": get_text(instruction, 'Company'),
            "Destino": get_text(instruction, 'DestinationName'), "Direccion": get_text(instruction, 'Address'),
            "Ciudad": get_text(instruction, 'City'), "ZIPCode": get_text(instruction, 'ZIPCode'),
            "State": get_text(instruction, 'State'), "Country": get_text(instruction, 'Country'),
            "Telefono": get_text(instruction, 'Phone'), "Contacto": get_text(instruction, 'Contact'),
            "Email": get_text(instruction, 'DestinationEmail'), "Costo_Envio": get_text(instruction, 'ShippingCost'),
            "ShippingCurrency": get_text(instruction, 'ShippingCurrency'), "TotalShippingCopies": get_text(instruction, 'TotalShippingCopies'),
            "Titulos": []
        }
        titles_to_send = instruction.find('TitlesToSend')
        if titles_to_send is not None:
            for title in titles_to_send.findall('Titles'):
                dest_info["Titulos"].append({
                    "TitleId": get_text(title, 'TitleId'), "Title": get_text(title, 'Title'),
                    "Copies": get_text(title, 'Copies'), "TotalWeight": get_text(title, 'TotalWeight')
                })
        shipping_instructions.append(dest_info)
    
    datos['datos_envio_json'] = json.dumps(shipping_instructions, ensure_ascii=False)

    order_type_xml = get_text(order_element, 'OrderType')
    printing_facility_number_xml = get_text(order_element, 'PrintingFacilityNumber')
    publisher_facility_xml = get_text(order_element, 'PublisherFacility')
    estado_odoo_inicial = mapeos.LOCAL_DB_STATUS_NO_APLICA
    es_edist = mapeos.BMG_ORDER_TYPE_EDIST in order_type_xml
    es_pod = not es_edist
    if (es_edist and printing_facility_number_xml == mapeos.FACILITY_ID) or \
       (es_pod and (printing_facility_number_xml == mapeos.FACILITY_ID or publisher_facility_xml == mapeos.BMG_PUBLISHER_FACILITY_LAD)):
        estado_odoo_inicial = mapeos.LOCAL_DB_STATUS_LISTO_PARA_SINCRONIZAR
    
    # --- CÁLCULO DE MATEMÁTICA PURA (COMISIONES) ---
    print(f"    -> Calculando comisiones para {datos['order_code']}-{datos['line_number']}...")
    try:
        resultados_finance = calcular_matematica_pura(datos)
        datos.update(resultados_finance)
    except Exception as e_finance:
        print(f"    -> ⚠️ Error en cálculo financiero: {e_finance}")
    # -----------------------------------------------

    datos['estado_odoo'] = estado_odoo_inicial

    conn = db_conn.conectar_db()
    if not conn: return
    cursor = conn.cursor()
    try:
        columnas = ', '.join(datos.keys())
        placeholders = ', '.join(['?']*len(datos))
        cursor.execute(f"INSERT INTO trabajos (estado, {columnas}) VALUES ('{mapeos.LOCAL_DB_STATUS_LISTADO}', {placeholders})", list(datos.values()))
    except sqlite3.IntegrityError:
        # Si el pedido ya existe (IntegrityError), no hacemos nada.
        # La lógica de actualización de estados la maneja script_02,
        # y no hay lógica implementada para actualizar otros datos del pedido en Odoo.
        pass
    conn.commit()
    conn.close()

def run():
    """
    Función principal del script.
    """
    print(f"--- Iniciando Script 1: Sincronización de Pedidos BMG (Modo: Solo Nuevos) [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        print("Conexión a API de BMG establecida.")
    except Exception as e:
        print(f"Error fatal al conectar con la API de BMG: {e}")
        return

    # 1. Obtener lista de pedidos de la API
    codigos_de_api = set()
    try:
        fecha_final_str = datetime.now().strftime('%Y%m%d')
        fecha_inicial_str = (datetime.now() - timedelta(days=mapeos.BMG_SYNC_DAYS_BACK)).strftime('%Y%m%d')
        order_data_element = cliente_wsdl.service.BMBillingInterface(
            FacilityID=mapeos.FACILITY_ID, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD, 
            FromDate=fecha_inicial_str, 
            ToDate=fecha_final_str
        )
        if order_data_element is not None:
            pedidos = order_data_element.findall('Order')
            if pedidos:
                nuevos_codigos = {p.find('OrderCode').text for p in pedidos if p.find('OrderCode') is not None}
                codigos_de_api.update(nuevos_codigos)
        print(f"Se encontraron {len(codigos_de_api)} pedidos recientes en la API.")
    except Exception as e:
        print(f"Error al obtener la lista de pedidos de la API: {e}")
        return

    # 2. Obtener lista de pedidos existentes en la DB
    try:
        conn = db_conn.conectar_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT order_code FROM trabajos")
        codigos_en_db = {row['order_code'] for row in cursor.fetchall()}
        conn.close()
        print(f"Se encontraron {len(codigos_en_db)} pedidos existentes en la base de datos local.")
    except Exception as e:
        print(f"Error al leer los pedidos existentes en la base de datos: {e}")
        return

    # 3. Determinar los pedidos realmente nuevos
    codigos_a_procesar = codigos_de_api - codigos_en_db
    
    # Si hay un pedido de prueba definido en mapeos, forzar su procesamiento
    if mapeos.TEST_ORDER_CODE:
        print(f"  -> MODO DE PRUEBA: Forzando procesamiento para el pedido {mapeos.TEST_ORDER_CODE}")
        # Se procesará solo el pedido de prueba, ya sea nuevo o para actualizarlo.
        codigos_a_procesar = {mapeos.TEST_ORDER_CODE}

    if not codigos_a_procesar:
        print("No hay pedidos nuevos para procesar.")
        print("--- Script 1 Finalizado ---")
        return
    
    print(f"Se procesarán {len(codigos_a_procesar)} pedidos realmente nuevos.")

    # 4. Procesar solo los nuevos
    for code in list(codigos_a_procesar):
        print(f"  - Procesando detalles para el pedido nuevo: {code}")
        try:
            resultado_detalle = cliente_wsdl.service.BMBillingByOrder(
                OrderCode=code, 
                FacilityUserId=mapeos.FACILITY_USER_ID, 
                Password=mapeos.PASSWORD
            )
            
            if resultado_detalle is None: continue
            order_element = resultado_detalle.find('Order')
            if order_element is None: continue

            lineas = order_element.findall('Orderline')
            if not lineas: continue

            for linea_element in lineas:
                sincronizar_linea_con_db(order_element, linea_element)
            
            print(f"    -> Pedido {code} con {len(lineas)} líneas CREADO en la base de datos.")

        except Exception as e:
            print(f"    -> Error fatal procesando detalles del pedido {code}: {e}")

    print("--- Script 1 Finalizado ---")

if __name__ == "__main__":
    run()