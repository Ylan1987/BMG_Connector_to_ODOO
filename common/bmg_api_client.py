# -*- coding: utf-8 -*-
"""
Módulo Cliente para la API SOAP de BMG.

Centraliza la conexión y las llamadas a la API de BMG.
"""
import logging
from zeep import Client
from datetime import datetime, timedelta
from . import mapeos

_logger = logging.getLogger(__name__)

def conectar_bmg():
    """Se conecta al WSDL de BMG y devuelve el objeto cliente."""
    try:
        cliente_wsdl = Client(mapeos.WSDL_URL)
        _logger.info("✅ Conexión a API de BMG (WSDL) establecida.")
        return cliente_wsdl
    except Exception as e:
        _logger.error(f"❌ Error fatal al conectar con la API de BMG: {e}")
        return None

def get_order_list(bmg_api_client):
    """Obtiene la lista de códigos de pedido de los últimos días."""
    try:
        fecha_final_str = datetime.now().strftime('%Y%m%d')
        fecha_inicial_str = (datetime.now() - timedelta(days=mapeos.BMG_SYNC_DAYS_BACK)).strftime('%Y%m%d')
        
        _logger.info(f"Buscando pedidos en BMG desde {fecha_inicial_str} hasta {fecha_final_str}...")
        order_data_element = bmg_api_client.service.BMBillingInterface(
            FacilityID=mapeos.FACILITY_ID, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD, 
            FromDate=fecha_inicial_str, 
            ToDate=fecha_final_str
        )
        
        if order_data_element and hasattr(order_data_element, 'findall'):
            pedidos = order_data_element.findall('Order')
            if pedidos:
                codigos = {p.find('OrderCode').text for p in pedidos if p.find('OrderCode') is not None}
                _logger.info(f"Se encontraron {len(codigos)} pedidos recientes en la API de BMG.")
                return codigos
        
        _logger.info("No se encontraron pedidos recientes en la API de BMG.")
        return set()

    except Exception as e:
        _logger.error(f"❌ Error al obtener la lista de pedidos de la API de BMG: {e}")
        return set()

def get_order_details(bmg_api_client, order_code):
    """Obtiene el XML con los detalles de un pedido específico."""
    try:
        resultado_detalle = bmg_api_client.service.BMBillingByOrder(
            OrderCode=order_code, 
            FacilityUserId=mapeos.FACILITY_USER_ID, 
            Password=mapeos.PASSWORD
        )
        return resultado_detalle
    except Exception as e:
        _logger.error(f"❌ Error fatal procesando detalles del pedido {order_code} desde BMG: {e}")
        return None
