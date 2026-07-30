# -*- coding: utf-8 -*-
"""
Auditoria de solo lectura: busca pedidos de venta BMG facturados al 100% que
tienen picking (entrega) y/o OF (orden de fabricacion) sin cerrar en Odoo.

Ver README.md en esta carpeta para el contexto completo.

Uso:
    python auditar_pedidos_abiertos.py
Genera: auditoria_resultado.json en esta misma carpeta.
"""
import odoorpc
import io
import json
import os

ODOO_URL = 'prod17.odoo.imprentadiagonal.com.uy'
ODOO_DB = 'odoo17_prod'
# Agregar credenciales para usarlo (usuario y password/API key de Odoo prod).
ODOO_USER = ''
ODOO_PASS = ''

CHUNK = 200
ESTADOS_CERRADOS = ('done', 'cancel')


def conectar_odoo():
    odoo = odoorpc.ODOO(ODOO_URL, protocol='jsonrpc+ssl', port=443)
    odoo.login(ODOO_DB, ODOO_USER, ODOO_PASS)
    return odoo


def auditar():
    odoo = conectar_odoo()

    # CRITERIO CLAVE: x_bmg_order_line > 0 (NO "!= False"). El campo es un
    # entero que en TODA linea de venta del sistema (sea BMG o no) tiene
    # default 0, y en Odoo "0 != False" es verdadero a nivel de dominio ORM
    # para un campo entero -> "!= False" deja pasar CUALQUIER linea de venta,
    # no solo las de BMG. El indicador real de "esta linea vino del pipeline
    # de BMG" es que x_bmg_order_line tenga un numero de linea real (> 0).
    line_ids = odoo.execute('sale.order.line', 'search', [['x_bmg_order_line', '>', 0]])
    lines = odoo.execute('sale.order.line', 'read', line_ids, ['order_id'])
    order_ids = sorted(set(l['order_id'][0] for l in lines if l.get('order_id')))

    orders = []
    for i in range(0, len(order_ids), CHUNK):
        chunk = order_ids[i:i + CHUNK]
        orders.extend(odoo.execute('sale.order', 'read', chunk,
                                    ['name', 'state', 'invoice_status', 'amount_total',
                                     'picking_ids', 'mrp_production_ids']))

    # Solo pedidos facturados por el 100% de su total.
    facturados = [o for o in orders if o['invoice_status'] == 'invoiced']

    all_picking_ids = sorted(set(pid for o in facturados for pid in o['picking_ids']))
    all_mrp_ids = sorted(set(mid for o in facturados for mid in o['mrp_production_ids']))

    pickings_by_id = {}
    for i in range(0, len(all_picking_ids), CHUNK):
        chunk = all_picking_ids[i:i + CHUNK]
        for p in odoo.execute('stock.picking', 'read', chunk, ['name', 'state', 'x_is_bmg_picking', 'picking_type_id']):
            pickings_by_id[p['id']] = p

    mrps_by_id = {}
    for i in range(0, len(all_mrp_ids), CHUNK):
        chunk = all_mrp_ids[i:i + CHUNK]
        for m in odoo.execute('mrp.production', 'read', chunk, ['name', 'state']):
            mrps_by_id[m['id']] = m

    # Ademas de sale.order.mrp_production_ids, buscamos por origin=nombre del
    # pedido: en pedidos viejos las OF "nietas" (ej. interior color de un
    # componente) pueden haber quedado con un procurement_group_id distinto
    # al del pedido y no aparecer en el campo estandar.
    nombres = [o['name'] for o in facturados]
    of_por_origin_ids = odoo.execute('mrp.production', 'search', [['origin', 'in', nombres]])
    of_por_origin = {}
    for i in range(0, len(of_por_origin_ids), CHUNK):
        chunk = of_por_origin_ids[i:i + CHUNK]
        for m in odoo.execute('mrp.production', 'read', chunk, ['name', 'state', 'origin']):
            of_por_origin.setdefault(m['origin'], []).append(m)

    resultado = []
    for o in facturados:
        pickings_abiertos = [pickings_by_id[pid] for pid in o['picking_ids']
                              if pid in pickings_by_id and pickings_by_id[pid]['state'] not in ESTADOS_CERRADOS]

        ofs_abiertas_dict = {}
        for mid in o['mrp_production_ids']:
            if mid in mrps_by_id and mrps_by_id[mid]['state'] not in ESTADOS_CERRADOS:
                ofs_abiertas_dict[mid] = mrps_by_id[mid]
        for m in of_por_origin.get(o['name'], []):
            if m['state'] not in ESTADOS_CERRADOS:
                ofs_abiertas_dict[m['id']] = m
        ofs_abiertas = list(ofs_abiertas_dict.values())

        if pickings_abiertos or ofs_abiertas:
            resultado.append({
                'name': o['name'],
                'state': o['state'],
                'total': o['amount_total'],
                'pickings': [{'name': p['name'], 'state': p['state'],
                               'x_is_bmg_picking': p['x_is_bmg_picking'],
                               'tipo': p['picking_type_id'][1] if p['picking_type_id'] else None}
                              for p in pickings_abiertos],
                'ofs': [{'name': m['name'], 'state': m['state']} for m in ofs_abiertas],
            })

    payload = {
        'total_lineas_bmg': len(line_ids),
        'total_pedidos_bmg': len(order_ids),
        'total_facturados': len(facturados),
        'rows': resultado,
    }

    out_path = os.path.join(os.path.dirname(__file__), 'auditoria_resultado.json')
    with io.open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    solo_picking = [r for r in resultado if r['pickings'] and not r['ofs']]
    solo_of = [r for r in resultado if r['ofs'] and not r['pickings']]
    ambos = [r for r in resultado if r['ofs'] and r['pickings']]

    print(f"Lineas BMG reales: {payload['total_lineas_bmg']}")
    print(f"Pedidos BMG distintos: {payload['total_pedidos_bmg']}")
    print(f"Facturados al 100%: {payload['total_facturados']}")
    print(f"Con algo sin cerrar: {len(resultado)}")
    print(f"  Solo picking abierto: {len(solo_picking)}")
    print(f"  Solo OF abierta: {len(solo_of)}")
    print(f"  Ambos abiertos: {len(ambos)}")
    print(f"\nGuardado en: {out_path}")

    return payload


if __name__ == '__main__':
    auditar()
