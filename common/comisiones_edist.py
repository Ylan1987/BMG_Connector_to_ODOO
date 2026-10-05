# -*- coding: utf-8 -*-
"""Recalculo de las comisiones de eDist cuando ya se conoce el pais del editor.

EL PROBLEMA DE ORDEN
  script_01 calcula las comisiones al sincronizar el pedido, pero en ese momento
  NO se sabe de que pais es el editor: detectar_origen_por_url() intenta
  adivinarlo pidiendo una imagen de portada a una URL armada con el publisher
  (108907) y la filial (143) HARDCODEADOS. Para cualquier otro editor esa URL no
  existe, devuelve 404 y la funcion cae en su "return ES" por defecto.
  Medido el 2026-10-05: las 4.092 lineas de Odoo con el campo cargado dicen ES.
  Ninguna dice UY. La rama es_uy del calculo nunca se ejecuto en produccion.

  El pais REAL aparece despues, cuando script_07 encuentra la carpeta del titulo
  en el NAS con encontrar_ruta_trabajo_dinamicamente(). Esa funcion no adivina:
  recorre /originales y devuelve la carpeta que existe de verdad.

      /originales/UY/128/108257/816723
                  ^^
                  pais del editor

  Verificado contra el "Filial Editor" del reporte de Comisiones de BMG:
  coinciden 982 de 982 lineas.

POR QUE ACA Y NO EN script_01
  - Llamar a encontrar_ruta_trabajo_dinamicamente() desde script_01 no sirve: la
    carpeta puede no estar pronta todavia cuando corre.
  - Pedirle el dato al reporte de BMG tampoco: ese reporte queda pronto mucho
    despues del cierre.
  Asi que el momento correcto es este: script_07, apenas resuelve la ruta.

QUE RECALCULA
  Solo lineas con order_type == 'eDistrib. 1 a 1'. OJO: NO alcanza con mirar
  business_unit — ese campo es la LISTA DE PRECIOS con la que se cotizo el
  pedido, no el negocio. Hay lineas con business_unit 'eDistribución (pBooks)' y
  order_type de POD que no llevan este calculo.

  Y solo si el pais cambia la cuenta, o sea si el editor resulta uruguayo: ahi
  x_total_bmg_terceros pasa a 0 y todo se suma a x_total_lad_uy. Si el editor es
  extranjero lo que calculo script_01 ya esta bien y no se toca nada.
"""
import logging
import sqlite3

from . import db_conn, mapeos

_logger = logging.getLogger(__name__)

CAMPOS = ['x_origen_pais', 'x_precio_canal', 'x_costo_impresion_uy',
          'x_comision_traer_libreria_uy', 'x_comision_traer_editor_uy',
          'x_comision_editor_uy', 'x_comision_traer_editor_bmg',
          'x_comision_editor_bmg', 'x_comision_bmg_propia',
          'x_total_bmg_terceros', 'x_total_bmg_propio', 'x_total_lad_uy']


def pais_de_ruta(ruta_trabajo):
    """'UY' de '/originales/UY/128/108257/816723'. None si no se puede leer."""
    partes = str(ruta_trabajo or '').replace('\\', '/').split('/')
    for i, p in enumerate(partes):
        if p == 'originales' and i + 1 < len(partes):
            cand = partes[i + 1]
            return cand if len(cand) == 2 and cand.isalpha() else None
    return None


def _precio(valor):
    """Igual que _precio_a_float de script_01: BMG manda '1,295.0000'."""
    if valor in (None, ''):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    return float(str(valor).replace(',', '').strip())


def calcular(pvp, p_canal, costo_imp, origen):
    """La misma matematica de calcular_matematica_pura (script_01), pero con el
    pais que vino de la ruta en vez del que adivina detectar_origen_por_url()."""
    es_uy = (origen == 'UY')
    com_lib = pvp * 0.05
    com_traer_ed = pvp * 0.05
    com_editor = pvp * 0.25
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
    if es_uy:
        # Editor uruguayo: lo trajimos nosotros, no le debemos nada a BMG.
        res['x_total_lad_uy'] = costo_imp + com_lib + com_traer_ed + com_editor
        res['x_total_bmg_terceros'] = 0
    else:
        res['x_total_lad_uy'] = costo_imp + com_lib
        res['x_total_bmg_terceros'] = com_traer_ed + com_editor
    res['x_comision_bmg_propia'] = p_canal - (res['x_total_lad_uy']
                                              + res['x_total_bmg_terceros'])
    res['x_total_bmg_propio'] = res['x_comision_bmg_propia']
    return res


def recalcular_si_corresponde(trabajo, ruta_trabajo, odoo_api=None):
    """Recalcula las comisiones de una linea si hace falta.

    Devuelve los valores escritos, o None si no habia nada que hacer.
    Nunca levanta: un fallo aca no puede frenar la generacion de la tapa.
    """
    try:
        if trabajo.get('order_type') != mapeos.BMG_ORDER_TYPE_EDIST_1_TO_1:
            return None

        origen = pais_de_ruta(ruta_trabajo)
        if not origen:
            return None

        guardado = trabajo.get('x_origen_pais')
        # Si ya esta guardado el pais correcto y hay comisiones, no se toca.
        if guardado == origen and _precio(trabajo.get('x_precio_canal')):
            return None

        pvp = _precio(trabajo.get('unit_price'))
        p_canal = _precio(trabajo.get('unit_price_channel'))
        costo = _precio(trabajo.get('unit_price_invoice'))
        if not pvp or not p_canal:
            return None

        vals = calcular(pvp, p_canal, costo, origen)

        conn = db_conn.conectar_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE trabajos SET %s WHERE order_code = ? AND line_number = ?"
            % ', '.join('%s = ?' % c for c in CAMPOS),
            [vals[c] for c in CAMPOS] + [trabajo['order_code'],
                                         trabajo['line_number']])
        conn.commit()
        conn.close()
        trabajo.update(vals)

        linea_odoo = trabajo.get('odoo_sale_order_line_id')
        if odoo_api and linea_odoo:
            odoo_api.env['sale.order.line'].browse(int(linea_odoo)).write(vals)

        _logger.info(
            "      -> Comisiones recalculadas para %s-%s: pais %s (antes %r), "
            "terceros %.2f, lad_uy %.2f",
            trabajo.get('order_code'), trabajo.get('line_number'), origen,
            guardado, vals['x_total_bmg_terceros'], vals['x_total_lad_uy'])
        print("      -> Comisiones recalculadas (%s): terceros %.2f, LAD %.2f"
              % (origen, vals['x_total_bmg_terceros'], vals['x_total_lad_uy']))
        return vals

    except Exception as e:
        _logger.error(
            "      -> No se pudieron recalcular las comisiones de %s-%s: %s: %s",
            trabajo.get('order_code'), trabajo.get('line_number'),
            type(e).__name__, e)
        return None
