import sys
sys.path.append('.')
from common import db_conn, meli_api

def limpiar_id(id_original, prefijo):
    if not id_original: return ''
    id_sin_prefijo = id_original[len(prefijo):] if id_original.startswith(prefijo) else id_original
    return id_sin_prefijo.lstrip('0')

def safe_float_conversion(value, default_value=0.0):
    if value is None: return default_value
    if isinstance(value, (int, float)): return float(value)
    if isinstance(value, str):
        try: return float(value.replace(',', ''))
        except ValueError: return default_value
    return default_value

def test_matching():
    # 1. Obtener pedido Meli (MOCK)
    print("Simulando datos de Meli para orden 2000017024811070 (mock)...")
    meli_data = {
        'raw_data': {
            'order_items': [
                {
                    'item': {'seller_custom_field': 'PAP12345-001', 'id': 'MLU1'},
                    'unit_price': 150.0
                },
                {
                    'item': {'seller_custom_field': 'PAP67890-XYZ', 'id': 'MLU2'},
                    'unit_price': 250.0
                },
                {
                    'item': {'seller_custom_field': '', 'id': 'MLU3'}, # sin seller_sku, buscaremos por isbn
                    'unit_price': 350.0
                }
            ]
        }
    }

    order_items = meli_data.get('raw_data', {}).get('order_items', [])
    print(f"Líneas encontradas en Meli (mock): {len(order_items)}")
    
    mock_bmg_trabajos = [
        {
            'line_number': 1,
            'title_id': '12345',
            'code': '9781234567890',
            'unit_price': 100.0
        },
        {
            'line_number': 2,
            'title_id': '67890',
            'code': '9780987654321',
            'unit_price': 100.0
        },
        {
            'line_number': 3,
            'title_id': '54321',
            'code': 'MLU3', # simulates an ISBN match since Meli ID is MLU3
            'unit_price': 100.0
        },
        {
            'line_number': 4,
            'title_id': '99999',
            'code': '9789999999999',
            'unit_price': 50.0
        }
    ]
    
    for idx, item in enumerate(order_items):
        item_info = item.get('item', {})
        sku = str(item_info.get('seller_custom_field') or item_info.get('id') or '')
        price = safe_float_conversion(item.get('unit_price', 0.0))
        print(f"  - Item Meli {idx}: SKU={sku}, Precio={price}")

    print(f"\nLíneas simuladas en BMG: {len(mock_bmg_trabajos)}")
    for t in mock_bmg_trabajos:
        print(f"  - Linea {t['line_number']}: TitleID: {t['title_id']}, Precio BMG: {t['unit_price']}")

    # 3. Aplicar lógica de matching propuesta
    print("\n--- APLICANDO LÓGICA DE MATCHING ---")
    for trabajo in mock_bmg_trabajos:
        isbn_bmg = str(trabajo.get('code') or '')
        pap_id_bmg = limpiar_id(trabajo.get('title_id'), 'PAP')
        precio_unitario_final = safe_float_conversion(trabajo.get('unit_price'))
        
        precio_ml = None
        matched_idx = -1
        
        for idx, item_line in enumerate(order_items):
            if item_line.get('_matched'):
                continue
                
            item_info = item_line.get('item', {})
            sku = str(item_info.get('seller_custom_field') or item_info.get('id') or '')
            
            if pap_id_bmg and pap_id_bmg in sku:
                precio_ml = safe_float_conversion(item_line.get('unit_price', 0.0))
                item_line['_matched'] = True
                matched_idx = idx
                break
            elif isbn_bmg and isbn_bmg in sku:
                precio_ml = safe_float_conversion(item_line.get('unit_price', 0.0))
                item_line['_matched'] = True
                matched_idx = idx
                break

        if precio_ml is not None:
            print(f"[EXITO] Línea BMG {trabajo['line_number']} (PAP: {pap_id_bmg}) hace match con ML Item {matched_idx}. Precio final ajustado a ML: {precio_ml}")
        else:
            print(f"[FALLO] Línea BMG {trabajo['line_number']} (PAP: {pap_id_bmg}) NO ENCONTRÓ MATCH en ML. Mantiene precio inicial de BMG: {precio_unitario_final}")

if __name__ == '__main__':
    # Usar cp1252 fix para prints en windows terminal
    test_matching()
