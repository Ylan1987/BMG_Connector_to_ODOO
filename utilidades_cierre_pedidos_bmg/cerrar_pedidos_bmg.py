# -*- coding: utf-8 -*-
"""
Cierra en Odoo las OF y/o pickings pendientes de un pedido BMG, y sincroniza
el estado real en BMG a "Entregado" (POD o eDist segun corresponda).

Ver README.md en esta carpeta para el contexto completo, el orden de pasos,
y los casos especiales a tener en cuenta ANTES de correr esto sobre pedidos
nuevos.

Uso basico (desde Python):

    from cerrar_pedidos_bmg import conectar_odoo, conectar_bmg, procesar_pedido_completo

    odoo = conectar_odoo()
    cliente_wsdl = conectar_bmg()
    resultado = procesar_pedido_completo(odoo, cliente_wsdl, 'P80450')
    print(resultado)

O por linea de comandos, pasando uno o mas nombres de pedido:

    python cerrar_pedidos_bmg.py P80450 P80451 P80473

IMPORTANTE: antes de correr esto sobre una tanda nueva de pedidos, revisar
primero con verificar_pickings_no_bmg() que ninguno tenga un picking abierto
que NO sea la entrega BMG normal (ej. una devolucion WH/IN) - ver README.
"""
import sys
import os
import datetime
import io
import json

sys.path.insert(0, r'C:\Users\ylana\Downloads\BMG\V2.0')

import odoorpc
from common import mapeos
from zeep import Client

ESTADOS_OK = {43, 204, 53, 205}  # Entregado POD/eDist, Facturado POD/eDist


def conectar_odoo():
    # Agregar credenciales para usarlo (usuario y password/API key de Odoo prod).
    ODOO_USER = ''
    ODOO_PASS = ''
    odoo = odoorpc.ODOO('prod17.odoo.imprentadiagonal.com.uy', protocol='jsonrpc+ssl', port=443)
    odoo.login('odoo17_prod', ODOO_USER, ODOO_PASS)
    return odoo


def conectar_bmg():
    return Client(mapeos.WSDL_URL)


def _orden_cierre(nombre_producto):
    """Orden obligatorio de cierre de OF: interior (color y/o ByN) -> tapa -> libro final.
    Cerrar en otro orden puede hacer fallar el 'Consumption Warning' o dejar
    componentes sin producir cuando el libro los necesita."""
    if nombre_producto.startswith('[COMP-INT-COLOR]') or nombre_producto.startswith('[INTERIOR]'):
        return 0
    if nombre_producto.startswith('[TAPA]'):
        return 1
    return 2


def verificar_pickings_no_bmg(odoo, nombres_pedidos):
    """Chequeo previo de seguridad (solo lectura): para una lista de nombres de
    pedido, devuelve los que tienen algun picking abierto que NO es la entrega
    BMG normal (x_is_bmg_picking=False) - ej. una devolucion WH/IN como la de
    P80450 el 30/07/2026. Esos hay que revisarlos a mano, NUNCA correr
    procesar_pedido_completo() sobre ellos sin revisar primero."""
    so_ids = odoo.execute('sale.order', 'search', [['name', 'in', nombres_pedidos]])
    sos = odoo.execute('sale.order', 'read', so_ids, ['name', 'picking_ids'])
    sospechosos = {}
    for so in sos:
        pks = odoo.execute('stock.picking', 'read', so['picking_ids'],
                            ['name', 'state', 'picking_type_id', 'x_is_bmg_picking'])
        abiertos = [p for p in pks if p['state'] not in ('done', 'cancel')]
        no_bmg = [p for p in abiertos if not p['x_is_bmg_picking']]
        if no_bmg:
            sospechosos[so['name']] = [(p['name'], p['picking_type_id'][1], p['state']) for p in no_bmg]
    return sospechosos


def cerrar_ofs(odoo, so_id, so_name, log):
    """Cierra todas las OF abiertas del pedido, en el orden interior->tapa->libro."""
    of_ids = odoo.execute('mrp.production', 'search', [['origin', '=', so_name]])
    so = odoo.execute('sale.order', 'read', [so_id], ['mrp_production_ids'])[0]
    of_ids = sorted(set(of_ids) | set(so['mrp_production_ids']))
    ofs = odoo.execute('mrp.production', 'read', of_ids, ['name', 'state', 'product_qty', 'workorder_ids', 'product_id'])
    abiertas = [o for o in ofs if o['state'] not in ('done', 'cancel')]
    abiertas.sort(key=lambda o: _orden_cierre(o['product_id'][1] if o['product_id'] else ''))

    workorder_ids_tocados = []
    ok, errores = [], []

    for mo in abiertas:
        log(f"    Cerrando OF {mo['name']} (id={mo['id']}, estado={mo['state']})")
        try:
            wos = odoo.execute('mrp.workorder', 'read', mo['workorder_ids'], ['name', 'state'])
            for wo in wos:
                if wo['state'] in ('done', 'cancel'):
                    continue
                workorder_ids_tocados.append(wo['id'])
                if wo['state'] not in ('progress',):
                    odoo.execute('mrp.workorder', 'button_start', [wo['id']])
                odoo.execute('mrp.workorder', 'button_finish', [wo['id']])

            odoo.execute('mrp.production', 'write', [mo['id']], {'qty_producing': mo['product_qty']})
            res = odoo.execute('mrp.production', 'button_mark_done', [mo['id']])

            # A veces Odoo compara lo que esta OF realmente consumio contra lo
            # que la Lista de Materiales dice AHORA que deberia consumir (la
            # LdM se reescribe en cada pedido nuevo que comparte esa variante
            # de libro - ver README). Eso dispara un wizard de confirmacion
            # en vez de cerrar directo; lo confirmamos con los mismos datos
            # que Odoo ya calculo.
            if isinstance(res, dict) and res.get('res_model') == 'mrp.consumption.warning':
                ctx = res.get('context', {})
                wizard_id = odoo.execute('mrp.consumption.warning', 'create', {
                    'mrp_production_ids': ctx.get('default_mrp_production_ids'),
                    'mrp_consumption_warning_line_ids': ctx.get('default_mrp_consumption_warning_line_ids'),
                })
                odoo.execute('mrp.consumption.warning', 'action_confirm', [wizard_id])

            mo_after = odoo.execute('mrp.production', 'read', [mo['id']], ['state', 'qty_produced'])[0]
            if mo_after['state'] == 'done':
                ok.append(mo['name'])
                log(f"      -> OK done ({mo_after['qty_produced']}/{mo['product_qty']})")
            else:
                errores.append(f"{mo['name']}: quedo en '{mo_after['state']}'")
                log(f"      -> ADVERTENCIA: quedo en '{mo_after['state']}'")
        except Exception as e:
            errores.append(f"{mo['name']}: {e}")
            log(f"      -> ERROR: {e}")

    return ok, errores, workorder_ids_tocados


def validar_pickings(odoo, so_id, log, forzar_cantidad=False):
    """Valida (marca como 'Hecho') los pickings BMG abiertos del pedido.

    Si hay algun picking abierto que NO sea BMG (x_is_bmg_picking=False),
    NO TOCA NADA y devuelve detener=True - ese pedido requiere revision manual.

    forzar_cantidad=True: si Odoo rechaza la validacion por "no hay
    cantidades reservadas" (tipico si el producto tiene ruta 'Buy' en vez de
    'Fabricar' - ver README, caso "Libros (copia)"), fuerza quantity =
    product_uom_qty en cada move y reintenta. Usar con criterio: confirma que
    el libro fisico se entrego aunque el stock de Odoo no lo respalde."""
    so = odoo.execute('sale.order', 'read', [so_id], ['picking_ids'])[0]
    pickings = odoo.execute('stock.picking', 'read', so['picking_ids'],
                             ['name', 'state', 'picking_type_id', 'x_is_bmg_picking'])
    abiertos = [p for p in pickings if p['state'] not in ('done', 'cancel')]

    no_bmg = [p for p in abiertos if not p['x_is_bmg_picking']]
    if no_bmg:
        return [], no_bmg, True

    ok, errores = [], []
    for p in abiertos:
        log(f"    Validando picking {p['name']} (id={p['id']}, estado={p['state']})")
        try:
            res = odoo.execute('stock.picking', 'button_validate', [p['id']])
            if isinstance(res, dict):
                errores.append(f"{p['name']}: devolvio wizard {res.get('res_model')} (no manejado)")
                continue
        except Exception as e:
            if forzar_cantidad and 'cantidades reservadas' in str(e):
                log(f"      -> sin reserva, forzando cantidad ({e})")
                moves = odoo.execute('stock.picking', 'read', [p['id']], ['move_ids'])[0]['move_ids']
                move_data = odoo.execute('stock.move', 'read', moves, ['product_uom_qty'])
                for m in move_data:
                    odoo.execute('stock.move', 'write', [m['id']], {'quantity': m['product_uom_qty']})
                try:
                    odoo.execute('stock.picking', 'button_validate', [p['id']])
                except Exception as e2:
                    errores.append(f"{p['name']}: {e2}")
                    log(f"      -> ERROR tras forzar: {e2}")
                    continue
            else:
                errores.append(f"{p['name']}: {e}")
                log(f"      -> ERROR: {e}")
                continue

        p_after = odoo.execute('stock.picking', 'read', [p['id']], ['state'])[0]
        if p_after['state'] == 'done':
            ok.append(p['name'])
            log(f"      -> OK done")
        else:
            errores.append(f"{p['name']}: quedo en '{p_after['state']}'")
            log(f"      -> ADVERTENCIA: quedo en '{p_after['state']}'")

    return ok, errores, False


def limpiar_cola(odoo, workorder_ids, so_id, desde_ts, log):
    """Borra SOLO las notificaciones 'pending' generadas por los workorders que
    tocamos (por id) y por este pedido desde que arrancamos el proceso - nunca
    entradas mas viejas ni de otros workorders, para no pisar actividad real
    de otra persona trabajando en paralelo."""
    total_borradas = 0
    if workorder_ids:
        q_ids = odoo.execute('bmg.notification.queue', 'search', [
            ['workorder_id', 'in', workorder_ids], ['state', '=', 'pending'],
        ])
        if q_ids:
            odoo.execute('bmg.notification.queue', 'unlink', q_ids)
            total_borradas += len(q_ids)

    q_ids2 = odoo.execute('bmg.notification.queue', 'search', [
        ['sale_order_id', '=', so_id], ['state', '=', 'pending'], ['create_date', '>=', desde_ts],
    ])
    if q_ids2:
        odoo.execute('bmg.notification.queue', 'unlink', q_ids2)
        total_borradas += len(q_ids2)

    log(f"    Borradas {total_borradas} entradas pending de la cola")
    return total_borradas


def chequear_y_corregir_bmg(odoo, cliente_wsdl, so_id, so_name, log):
    """Consulta el estado REAL y actual en BMG (no lo que nosotros mandamos
    antes) y, si esta atrasado respecto a Entregado/Facturado, lo corrige
    mandando 'Entregado' directamente por la API (POD=43, eDist=204),
    determinando POD/eDist por sale_order.opportunity_id.x_order_type."""
    so = odoo.execute('sale.order', 'read', [so_id], ['client_order_ref', 'opportunity_id'])[0]
    order_code = so['client_order_ref']
    if not order_code:
        log(f"    Sin client_order_ref, no se puede chequear BMG.")
        return None

    es_edist = False
    if so.get('opportunity_id'):
        opp = odoo.execute('crm.lead', 'read', [so['opportunity_id'][0]], ['x_order_type'])[0]
        es_edist = opp.get('x_order_type') == 'eDistrib. 1 a 1'

    resultado = cliente_wsdl.service.BMBillingByOrder(OrderCode=order_code, FacilityUserId=mapeos.FACILITY_USER_ID, Password=mapeos.PASSWORD)
    order_element = resultado.find('Order') if resultado is not None else None
    if order_element is None:
        log(f"    Sin respuesta valida de BMG para {order_code}.")
        return None

    lineas = order_element.findall('Orderline')
    entregado_id = 204 if es_edist else 43
    corregidas = []
    for linea in lineas:
        ln = linea.find('LineNumber'); ls = linea.find('LineStatus'); lsid = linea.find('LineStatusId')
        line_num = int(ln.text) if ln is not None else 1
        status_id = int(lsid.text) if lsid is not None else None
        log(f"    Linea {line_num}: {ls.text if ls is not None else '?'} (ID={status_id})")
        if status_id not in ESTADOS_OK:
            cliente_wsdl.service.BMBillingStatusChange(
                OrderCode=order_code, OrderLine=line_num, StatusId=entregado_id,
                FacilityUserId=mapeos.FACILITY_USER_ID, Password=mapeos.PASSWORD, Comments=""
            )
            log(f"      -> Corregido a Entregado (ID={entregado_id}) en linea {line_num}")
            corregidas.append(line_num)
    return corregidas


def procesar_pedido_completo(odoo, cliente_wsdl, so_name, log=print, forzar_cantidad_picking=False):
    """Proceso completo para UN pedido:
      1. Chequeo de seguridad: si tiene un picking abierto no-BMG, no toca
         nada y devuelve 'requiere_revision_manual'.
      2. Cierra las OF abiertas (interior -> tapa -> libro).
      3. Valida el/los picking(s) BMG abiertos.
      4. Borra de la cola de notificaciones SOLO lo generado en este proceso.
      5. Chequea el estado real en BMG y lo corrige a Entregado si esta atrasado.
    """
    log(f"\n=== Procesando {so_name} ===")
    so_ids = odoo.execute('sale.order', 'search', [['name', '=', so_name]])
    if not so_ids:
        log("  No se encontro el pedido.")
        return {'so_name': so_name, 'error_fatal': 'pedido no encontrado'}
    so_id = so_ids[0]
    desde_ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    so = odoo.execute('sale.order', 'read', [so_id], ['picking_ids'])[0]
    pickings_info = odoo.execute('stock.picking', 'read', so['picking_ids'],
                                  ['name', 'state', 'picking_type_id', 'x_is_bmg_picking'])
    no_bmg = [p for p in pickings_info if p['state'] not in ('done', 'cancel') and not p['x_is_bmg_picking']]
    if no_bmg:
        log(f"    !!! DETENIDO SIN TOCAR NADA: picking(s) no-BMG sin cerrar: "
            f"{[(p['name'], p['picking_type_id'][1]) for p in no_bmg]}")
        return {
            'so_name': so_name,
            'requiere_revision_manual': [(p['name'], p['picking_type_id'][1], p['state']) for p in no_bmg],
        }

    ok, errores, wo_tocados = cerrar_ofs(odoo, so_id, so_name, log)
    pick_ok, pick_err, _ = validar_pickings(odoo, so_id, log, forzar_cantidad=forzar_cantidad_picking)
    limpiar_cola(odoo, wo_tocados, so_id, desde_ts, log)
    corregidas = chequear_y_corregir_bmg(odoo, cliente_wsdl, so_id, so_name, log)

    return {
        'so_name': so_name,
        'pickings_ok': pick_ok, 'pickings_error': pick_err,
        'ofs_ok': ok, 'ofs_error': errores,
        'lineas_corregidas': corregidas,
    }


def procesar_lote(nombres_pedidos, forzar_cantidad_picking=False):
    """Punto de entrada para procesar una lista de pedidos de una sola vez.
    Guarda el resultado incremental en lote_resultados.json (misma carpeta)."""
    odoo = conectar_odoo()
    cliente_wsdl = conectar_bmg()

    sospechosos = verificar_pickings_no_bmg(odoo, nombres_pedidos)
    if sospechosos:
        print("!!! ATENCION: estos pedidos tienen pickings no-BMG y NO se van a tocar:")
        for k, v in sospechosos.items():
            print(f"  {k}: {v}")
        nombres_pedidos = [n for n in nombres_pedidos if n not in sospechosos]
        print(f"\nContinuando solo con los {len(nombres_pedidos)} pedidos limpios.\n")

    resultados = []
    out_path = os.path.join(os.path.dirname(__file__), 'lote_resultados.json')
    for nombre in nombres_pedidos:
        try:
            r = procesar_pedido_completo(odoo, cliente_wsdl, nombre, forzar_cantidad_picking=forzar_cantidad_picking)
        except Exception as e:
            r = {'so_name': nombre, 'error_fatal': str(e)}
        resultados.append(r)
        with io.open(out_path, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)

    print(f"\nTerminado: {len(resultados)} pedidos. Detalle en {out_path}")
    return resultados


if __name__ == '__main__':
    nombres = sys.argv[1:]
    if not nombres:
        print("Uso: python cerrar_pedidos_bmg.py P80450 P80451 ...")
        sys.exit(1)
    procesar_lote(nombres)
