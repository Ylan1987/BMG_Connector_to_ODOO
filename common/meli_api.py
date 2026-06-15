# -*- coding: utf-8 -*-
"""
Módulo auxiliar para interactuar con la API de MercadoLibre Uruguay.
Permite obtener costos de envío y buscar ventas específicas.
"""

import requests
import logging
import json
import os
import time
from . import mapeos

_logger = logging.getLogger(__name__)

TOKEN_FILE = 'meli_tokens.json'

def _guardar_tokens(data):
    """Guarda los tokens en un archivo JSON local."""
    try:
        # Añadir timestamp de expiración aproximado (ahora + expires_in)
        data['expires_at'] = time.time() + data.get('expires_in', 21600)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        _logger.error(f"Error al guardar meli_tokens.json: {e}")
        return False

def _cargar_tokens():
    """Carga los tokens del archivo JSON local."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def sincronizar_token_con_odoo(access_token):
    """Envía el access_token a Odoo para que el módulo de etiquetas pueda usarlo."""
    try:
        from . import odoo_conn
        odoo = odoo_conn.conectar_odoo()
        if odoo:
            param_key = 'nesta_meli_shipping.meli_access_token'
            
            # Buscar si ya existe usando el método de bajo nivel
            ids = odoo.execute('ir.config_parameter', 'search', [('key', '=', param_key)])
            
            if ids:
                # Actualizar existente
                odoo.execute('ir.config_parameter', 'write', ids[0], {'value': access_token})
            else:
                # Crear nuevo
                odoo.execute('ir.config_parameter', 'create', {'key': param_key, 'value': access_token})
                
            print("    -> [MELI] ✅ Token sincronizado con Odoo con éxito.")
    except Exception as e:
        _logger.error(f"Error al sincronizar token con Odoo: {e}")

def refrescar_token(refresh_token):
    """Intercambia el refresh_token por uno nuevo."""
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': mapeos.MELI_CLIENT_ID,
        'client_secret': mapeos.MELI_CLIENT_SECRET,
        'refresh_token': refresh_token
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            _guardar_tokens(data)
            _logger.info("✅ Token de Mercado Libre refrescado con éxito.")
            
            # Sincronizar con Odoo
            sincronizar_token_con_odoo(access_token)
            
            return access_token
        else:
            _logger.error(f"❌ Error al refrescar token ML: {response.status_code} - {response.text}")
    except Exception as e:
        _logger.error(f"❌ Error de conexión al refrescar token ML: {e}")
    return None

def obtener_access_token(forzar_sync_odoo=False):
    """
    Obtiene el access token vigente. 
    Busca en el archivo local, si faltan menos de 30 minutos para vencer lo refresca automáticamente.
    Si forzar_sync_odoo es True, envía el token a Odoo incluso si no hubo refresco.
    """
    tokens = _cargar_tokens()
    
    if tokens:
        access_token = tokens.get('access_token')
        expires_at = tokens.get('expires_at', 0)
        tiempo_restante = expires_at - time.time()

        # Si faltan menos de 30 minutos (1800 seg) para vencer o ya venció, refrescar
        if tiempo_restante < 1800:
            print(f"    -> [MELI] Token próximo a vencer ({int(tiempo_restante/60)} min). Refrescando...")
            return refrescar_token(tokens.get('refresh_token'))
        
        if forzar_sync_odoo:
            sincronizar_token_con_odoo(access_token)
            
        return access_token

    # Fallback: Si no hay archivo, pero hay un token en mapeos (primer uso)
    return getattr(mapeos, 'MELI_ACCESS_TOKEN', None)

def obtener_detalle_orden_ml(meli_order_id):
    """
    Consulta a la API de ML por el detalle completo de una orden.
    Devuelve un diccionario con el costo de envío y un mapeo de precios por SKU/ISBN.
    """
    token = obtener_access_token()
    if not token or not meli_order_id:
        return None

    url = f"https://api.mercadolibre.com/orders/{meli_order_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # 1. Extraer costo de envío (buscamos en cabecera y luego sumamos todos los pagos)
            shipping_data = data.get('shipping', {})
            costo_envio = shipping_data.get('cost')
            
            # Si en cabecera es 0 o None, buscamos en los pagos (pueden ser varios)
            if not costo_envio:
                costo_envio = 0.0
                approved_payments = [p for p in data.get('payments', []) if p.get('status') == 'approved']
                for payment in approved_payments:
                    p_cost = payment.get('shipping_cost')
                    if p_cost:
                        costo_envio += float(p_cost)
                
                # [FIX] Si sigue siendo 0, intentamos consultar el shipment directamente
                if costo_envio == 0 and shipping_data.get('id'):
                    ship_id = shipping_data['id']
                    ship_url = f"https://api.mercadolibre.com/shipments/{ship_id}"
                    try:
                        ship_res = requests.get(ship_url, headers=headers, timeout=10)
                        if ship_res.status_code == 200:
                            ship_data = ship_res.json()
                            ship_cost = ship_data.get('shipping_option', {}).get('cost')
                            if ship_cost:
                                costo_envio = float(ship_cost)
                                print(f"    [DEBUG_MELI] ✅ Costo de envío recuperado del SHIPMENT {ship_id}: {costo_envio}")
                    except Exception as e:
                        print(f"    [DEBUG_MELI] ❌ Error al consultar shipment {ship_id}: {e}")

                if costo_envio == 0:
                    print(f"    [DEBUG_MELI] ⚠️ No se encontró costo de envío en pagos ni en shipment.")
            
            # 2. Extraer precios de ítems y validar total
            items_precios = {}
            suma_items = 0.0
            for item_line in data.get('order_items', []):
                item_info = item_line.get('item', {})
                sku = item_info.get('seller_custom_field') or item_info.get('id')
                unit_price = float(item_line.get('unit_price', 0.0))
                qty = int(item_line.get('quantity', 1))
                suma_items += (unit_price * qty)
                if sku:
                    items_precios[sku] = unit_price
            
            # 3. VALIDACIÓN CONTABLE
            # Nota: En Mercado Envíos 2, el paid_amount de la orden a veces NO incluye el envío si ML lo cobra aparte.
            total_pagado = float(data.get('paid_amount', 0.0))
            esperado = suma_items + costo_envio
            diff = abs(esperado - total_pagado)
            
            if diff > 0.1:
                # Si la diferencia es exactamente el costo de envío, es que ML lo cobró por fuera de la orden
                if abs(suma_items - total_pagado) < 0.1:
                    print(f"    [MELI] ℹ️ El envío ({costo_envio}) fue cobrado por fuera de la orden. Total pagado items: {total_pagado}")
                else:
                    print(f"    [MELI] ❌ DESAJUSTE: Items({suma_items}) + Envío({costo_envio}) = {esperado} != Pagado({total_pagado})")
            else:
                print(f"    [MELI] ✅ Validación contable OK: {total_pagado} UYU")

            print(f"    -> [MELI] Detalle obtenido para orden {meli_order_id}. Envío: {costo_envio}. Ítems: {len(items_precios)}")
            
            return {
                'shipping_cost': costo_envio,
                'items_prices': items_precios,
                'total_paid': total_pagado,
                'raw_data': data
            }
    except Exception as e:
        _logger.error(f"    -> [MELI] Error al consultar detalle de orden {meli_order_id}: {e}")
    
    return None

def obtener_seller_id():
    """Obtiene el ID del vendedor autenticado."""
    token = obtener_access_token()
    if not token: return None
    try:
        response = requests.get("https://api.mercadolibre.com/users/me", headers={'Authorization': f'Bearer {token}'}, timeout=10)
        if response.status_code == 200:
            return response.json().get('id')
    except Exception as e:
        _logger.error(f"    -> [MELI] Error al obtener seller_id: {e}")
    return None
