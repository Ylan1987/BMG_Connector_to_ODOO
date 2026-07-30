# -*- coding: utf-8 -*-
"""
Archivo de configuración central para los mapeos.
Ambos scripts (procesador y sincronizador) importarán los
diccionarios desde aquí.
"""

import os
import json
import logging
from . import config_log
from datetime import datetime, timedelta

# ============================================================================
# --- CONFIGURACIÓN GENERAL Y DE ENTORNO ---
# ============================================================================

# Ruta al archivo de base de datos SQLite local.
DB_FILE = '/app/trabajos.db'

# Ruta de almacenamiento base para los archivos generados en el servidor.
SERVER_REAL = r'\\NASDiagonal1\Trabajos\LAD'

# Rutas de destino para los archivos de tapa e interior generados.
DEST_PATH_TAPAS = r'/salida/LAD/Tapas'
DEST_PATH_INTERIOR = r'/salida/LAD/Interior'
BASE_STORAGE_PATH = r'/originales'

# ============================================================================
# --- CONFIGURACIÓN DE ODOO (Conexión y Credenciales) ---
# ============================================================================

ODOO_URL = 'testkrl.odoo.imprentadiagonal.com.uy'
ODOO_DB = 'odoo17_stage'
ODOO_USUARIO = 'ylan.archimowicz@imprentadiagonal.com.uy'
ODOO_CONTRASENA = '77436602dbb10c3959d3cf28e12e0cf4d253f667'

MERCADOLIBROS_CHANNEL_ID = '236'
ODOO_JOURNAL_MERCADOPAGO = 'MercadoPago'
PRODUCTO_PLANTILLA_LIBRO = "Libro Bajo Demanda"
PRODUCTO_PLANTILLA_LIBRO_FUERA_UY = "Libro Bajo Demanda fuera de UY"

MAPEO_LAMINADO = {
    'LAMBTE': 'Laminado Brillo',
    'LAMMAT': 'Laminado Mate',
    'LAMBAR': 'Barnizado',
    'LAMBBR': 'Barniz brillo a registro',
    'LAMGOF': 'Laminado Gofrado',
    'LAMUV': 'Laminado UV'
}

MAPEO_ENCUADERNADO = {
    'ENCACA': 'Cosido con 2 grapas',
    'ENCACA0': 'Cosido con 2 grapas',
    'ENCBIN': 'Lomo cuadrado',
    'ENCCOS': 'Cosido a hilo',
    'ENCCOS0': 'Cosido a hilo',
    'ENCDOB': 'Doblado',
    'ENCDUR': 'Tapa Dura',
    'ENCESP': 'Rulo metálico',
    'ENCESP0': 'Rulo metálico',
    'ENCEST': 'Rulo metálico con tapa plástica',
    'ENCPUR': 'Lomo cuadrado',
    'ENCWIR': 'Rulo metálico'
}

MAPEO_IMPRESION_TAPA = {
    'CO40': 'Tapa Full Color Simple Faz',
    'CO41': 'Tapa Full Color Doble Faz',
    'CO44': 'Tapa Full Color Doble Faz',
    'BN10': 'Tapa Blanco y Negro Simple faz',
    'BN11': 'Tapa Blanco y Negro Doble faz',
}

# ============================================================================
# --- CONFIGURACIÓN DE BMG (Conexión y Credenciales) ---
# ============================================================================

WSDL_URL = 'http://wsbmg.bibliomanager.com/BGK20WS.asmx?WSDL'
FACILITY_ID = '128'
FACILITY_USER_ID = 'ylan'
PASSWORD = 'p4ssw0rdl4d'

MAPEO_NOMBRES_PAPEL = {
    "BNAHS070": "Ahuesado Ecologico 70", "BNAHS080": "Ahuesado Ecologico 80", "BNAHS090": "Ahuesado Ecologico 90", "BNAHU065": "Ahuesado 65" , "BNAHU070": "Ahuesado 70" , "BNAHU080": "Ahuesado 80" , "BNAHU090": "Ahuesado Ecologico 90", "BNAHU100": "Ahuesado 100" , "BNAHU125": "Ahuesado 125" , "BNAHV080": "Ahuesado 80" , "BNAHV090": "Ahuesado 90" , "BNAUT080": "Ahuesado 80" , "BNBIB045": "Obra 45", "BNCBD090": "Obra 90" , "BNCHA056": "Obra 56" , "BNCHA063": "Obra 63" , "BNCHA075": "Obra 75" , "BNCHA090": "Obra 90" , "BNCHA120": "Obra 120" , "BNCHA180": "Obra 180" , "BNCHA240": "Obra 240" , "BNCRE056": "Ahuesado 60" , "BNEAR070": "Ahuesado Ecologico 70", "BNEAR090": "Obra 80" , "BNHOL052": "Ahuesado 52" , "BNHOL055": "Ahuesado 55" , "BNILB090": "Coteado 90" , "BNILB115": "Coteado 115" , "BNILB125": "Coteado 130" , "BNILB135": "Coteado 130" , "BNILB150": "Coteado 150" , "BNILB170": "Coteado 170" , "BNILB230": "Coteado 230" , "BNILM080": "Coteado Mate 80" , "BNILM090": "Coteado Mate 90" , "BNILM115": "Coteado 115" , "BNILM125": "Coteado Mate 130" , "BNILM135": "Coteado Mate 130" , "BNILM150": "Coteado 150" , "BNILM170": "Coteado Mate 170" , "BNILM230": "Coteado Mate 230" , "BNNAT090": "Obra 90" , "BNNET100": "Obra 100" , "BNOBR040": "Obra 40" , "BNOBR050": "Obra 50" , "BNOBR056": "Obra 56" , "BNOBR060": "Obra 60" , "BNOBR063": "Obra 63" , "BNOBR070": "Obra 70" , "BNOBR075": "Obra 75" , "BNOBR080": "Obra 80" , "BNOBR090": "Obra 90" , "BNOBR100": "Obra 100" , "BNOBR110": "Obra 100" , "BNOBR120": "Obra 120" , "BNOBR130": "Obra 100" , "BNOBR150": "Obra 150" , "BNOPT050": "Obra 50" , "BNOPT075": "Obra 75" , "BNREC075": "Reciclado 75" , "BNREC100": "Reciclado 100" , "BNREC120": "Reciclado 120" , "BNREC240": "Reciclado 240" , "BNREG112": "Ahuesado 112" , "BNREG140": "Ahuesado 140" , "BNRLT090": "Reciclado 90",
    "COAHS070": "Ahuesado Ecologico 70", "COAHS080": "Ahuesado Ecologico 80", "COAHS090": "Ahuesado Ecologico 90", "COAHU065": "Ahuesado 65" , "COAHU070": "Ahuesado 70" , "COAHU080": "Ahuesado 80" , "COAHU090": "Ahuesado Ecologico 90", "COAHU100": "Ahuesado 100" , "COAHU125": "Ahuesado 125" , "COAHV080": "Ahuesado 80" , "COAHV090": "Ahuesado 90" , "COAUT080": "Ahuesado 80" , "COBIB045": "Obra 45", "COCBD090": "Obra 90" , "COCHA056": "Obra 56" , "COCHA063": "Obra 63" , "COCHA075": "Obra 75" , "COCHA090": "Obra 90" , "COCHA120": "Obra 120" , "COCHA180": "Obra 180" , "COCHA240": "Obra 240" , "COCRE056": "Ahuesado 60" , "COEAR70": "Ahuesado Ecologico 70", "COEAR90": "Obra 80" , "COHOL052": "Ahuesado 52" , "COHOL055": "Ahuesado 55" , "COILB090": "Coteado 90" , "COILB115": "Coteado 115" , "COILB125": "Coteado 130" , "COILB135": "Coteado 130" , "COILB150": "Coteado 150" , "COILB170": "Coteado 170" , "COILB230": "Coteado 230" , "COILM080": "Coteado Mate 80" , "COILM090": "Coteado Mate 90" , "COILM115": "Coteado 115" , "COILM125": "Coteado Mate 130" , "COILM135": "Coteado Mate 130" , "COILM150": "Coteado 150" , "COILM170": "Coteado Mate 170" , "COILM230": "Coteado Mate 230" , "CONAT090": "Obra 90" , "CONET100": "Obra 100" , "COOBR040": "Obra 40" , "COOBR050": "Obra 50" , "COOBR056": "Obra 56" , "COOBR060": "Obra 60" , "COOBR063": "Obra 63" , "COOBR070": "Obra 70" , "COOBR075": "Obra 75" , "COOBR080": "Obra 80" , "COOBR090": "Obra 90" , "COOBR100": "Obra 100" , "COOBR110": "Obra 100" , "COOBR120": "Obra 120" , "COOBR130": "Obra 100" , "COOBR150": "Obra 150" , "COOPT050": "Obra 50" , "COOPT075": "Obra 75" , "COREC075": "Reciclado 75" , "COREC100": "Reciclado 100" , "COREC120": "Reciclado 120" , "COREC240": "Reciclado 240" , "COREG112": "Ahuesado 112" , "COREG140": "Ahuesado 140" , "CORLT090": "Reciclado 90",
    "TACAP250": "Cartulina 250", "TACAR240": "Cartulina 240", "TACAR300": "Cartulina 300",
    "TACHA180": "Chamol 180", "TACONS280": "Cons 280", "TADUCAR": "Tapa Dura Cartoné", "TAEAR200": "Ahuesado Ecologico 200", "TAESM250": "Esmaltado 250",
    "TAESM280": "Esmaltado 280", "TAESM320": "Esmaltado 320", "TAILB115": "Coteado 115", "TAILB150": "Coteado 150", "TAILB170": "Coteado 170",
    "TAILB230": "Coteado 230", "TAILB300": "Coteado 300", "TAILM115": "Coteado Mate 115", "TAILM150": "Coteado Mate 150", "TAILM170": "Coteado Mate 170",
    "TAILM230": "Coteado Mate 230", "TAILM250": "Coteado Mate 250", "TAILU200": "Ilustración 200", "TAILU250": "Ilustración 250", "TAILU270": "Ilustración 270",
    "TAILU350": "Ilustración 350", "TAMOD260": "Mod 260", "TAOBR180": "Obra 180", "TAOBR240": "Obra 240", "TAORO300": "Oro 300",
    "TAREC240": "Reciclado 240", "TAREC300": "Reciclado 300", "TAREV270": "Reverso 270", "TARLT250": "RLT 250", "TASBS220": "SBS 220",
    "TASBS250": "SBS 250", "TASBS270": "SBS 270", "TASBS280": "SBS 280", "TATEX012": "Tex 012", "TATEX014": "Tex 014",
    "TATINCAM": "Tincam", "TATINCEY": "Tincey", "TAVER300B": "Ver 300B", "TAVER300C": "Ver 300C", "TAVER300N": "Ver 300N"
}

MAPEO_PAPEL = {
    "BNAHS070": "AE70", "BNAHS080": "AE80", "BNAHS090": "AE90", "BNAHU065": "A65", "BNAHU070": "A70",
    "BNAHU080": "A80", "BNAHU090": "AE90", "BNAHU100": "A100", "BNAHU125": "A125", "BNAHV080": "A80",
    "BNAHV090": "A90", "BNAUT080": "AD80", "BNBIB045": "B45", "BNCBD090": "O90", "BNCHA056": "O56",
    "BNCHA063": "O63", "BNCHA075": "O75", "BNCHA090": "O90", "BNCHA120": "O120", "BNCHA180": "O180",
    "BNCHA240": "O240", "BNCRE056": "A60", "BNEAR070": "AE70", "BNEAR090": "O80", "BNHOL052": "A52",
    "BNHOL055": "A55", "BNILB090": "C90", "BNILB115": "C115", "BNILB125": "C125", "BNILB135": "C135",
    "BNILB150": "C150", "BNILB170": "C170", "BNILB230": "C230", "BNILM080": "CM80", "BNILM090": "CM90",
    "BNILM115": "C115", "BNILM125": "CM125", "BNILM135": "CM135", "BNILM150": "C150", "BNILM170": "CM170",
    "BNILM230": "CM230", "BNNAT090": "O90", "BNNET100": "O100", "BNOBR040": "O40", "BNOBR050": "O50",
    "BNOBR056": "O56", "BNOBR060": "O60", "BNOBR063": "O63", "BNOBR070": "O70", "BNOBR075": "O75",
    "BNOBR080": "O80", "BNOBR090": "O90", "BNOBR100": "O100", "BNOBR110": "O100", "BNOBR120": "O120",
    "BNOBR130": "O100", "BNOBR150": "O150", "BNOPT050": "O50", "BNOPT075": "O75", "BNREC075": "R75",
    "BNREC100": "R100", "BNREC120": "R120", "BNREC240": "R240", "BNREG112": "A112", "BNREG140": "A140",
    "BNRLT090": "R90", "COAHS070": "AE70", "COAHS080": "AE80", "COAHS090": "AE90", "COAHU065": "A65",
    "COAHU070": "A70", "COAHU080": "A80", "COAHU090": "AE90", "COAHU100": "A100", "COAHU125": "A125",
    "COAHV080": "A80", "COAHV090": "A90", "COAUT080": "AD80", "COBIB045": "B45", "COCBD090": "O90",
    "COCHA056": "O56", "COCHA063": "O63", "COCHA075": "O75", "COCHA090": "O90", "COCHA120": "O120",
    "COCHA180": "O180", "COCHA240": "O240", "COCRE056": "A60", "COEAR070": "AE70", "COEAR090": "O80",
    "COHOL052": "A52", "COHOL055": "A55", "COILB090": "C90", "COILB115": "C115", "COILB125": "C125",
    "COILB135": "C135", "COILB150": "C150", "COILB170": "C170", "COILB230": "C230", "COILM080": "CM80",
    "COILM090": "CM90", "COILM115": "C115", "COILM125": "CM125", "COILM135": "CM135", "COILM150": "C150",
    "COILM170": "CM170", "COILM230": "CM230", "CONAT090": "O90", "CONET100": "O100", "COOBR040": "O40",
    "COOBR050": "O50", "COOBR056": "O56", "COOBR060": "O60", "COOBR063": "O63", "COOBR070": "O70",
    "COOBR075": "O75", "COOBR080": "O80", "COOBR090": "O90", "COOBR100": "O100", "COOBR110": "O100",
    "COOBR120": "O120", "COOBR130": "O100", "COOBR150": "O150", "COOPT050": "O50", "COOPT075": "O75",
    "COREC075": "R75", "COREC100": "R100", "COREC120": "R120", "COREC240": "R240", "COREG112": "A112",
    "COREG140": "A140", "CORLT090": "R90", "COAHU115": "A115", "COAUT150": "AD150", "COEAR70": "AE80",
    "COEAR90": "O80", "COINS150": "C150", "CONER100": "O100", "CONNAT090": "O100", "COOBR180": "O180",
    "COOBR240": "O240", "-- Sin tapa --": "Sin", "TACAP250": "270", "TACAR240": "270", "TACAR300": "270",
    "TACHA180": "270", "TACONS280": "270", "TADUCAR": "Dura", "TAEAR200": "270", "TAESM250": "270",
    "TAESM280": "270", "TAESM320": "270", "TAILB115": "C115", "TAILB150": "C150", "TAILB170": "C170",
    "TAILB230": "C230", "TAILB300": "270", "TAILM115": "CM115", "TAILM150": "CM150", "TAILM170": "CM170",
    "TAILM230": "CM230", "TAILM250": "CM250", "TAILU200": "CM200", "TAILU250": "CM250", "TAILU270": "270",
    "TAILU350": "270", "TAMOD260": "270", "TAOBR180": "270", "TAOBR240": "270", "TAORO300": "270",
    "TAREC240": "R240", "TAREC300": "R240", "TAREV270": "270", "TARLT250": "270", "TASBS220": "270",
    "TASBS250": "270", "TASBS270": "270", "TASBS280": "270", "TATEX012": "270", "TATEX014": "270",
    "TATINCAM": "270", "TATINCEY": "270", "TAVER300B": "270", "TAVER300C": "270", "TAVER300N": "270"
}

# ============================================================================
# --- CONFIGURACIÓN DE EMAIL (Notificaciones) ---
# ============================================================================

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USUARIO = 'diagonalimprenta@gmail.com'
SMTP_CONTRASENA = 'sofalzjoktlqhsqo'
EMAIL_DESTINO = 'info@imprentadiagonal.com.uy'

# ============================================================================
# MAPEOS PARA SISTEMA DE FABRICACIÓN DINÁMICA
# ============================================================================

MAPEO_CENTROS_TRABAJO = {
    'IMPRESORA_8420': '__export__.mrp_workcenter_impresora_digital_n_8100s',
    'IMPRESORA_8310': '__export__.mrp_workcenter_impresora_digital_n_8310s',
    'IMPRESORA_7200': '__export__.mrp_workcenter_impresora_digital_color_7200x',
    'GUILLOTINA': '__export__.mrp_workcenter_guillotina_principal_polar_mohr',
    'LAMINADORA': '__export__.mrp_workcenter_laminadora_automatica',
    'MESA_MULTITAREA': '__export__.mrp_workcenter_mesa_multitarea_auxiliar',
    'ENCUADERNADORA_HORIZON': '__export__.mrp_workcenter_horizon',
    'EMPAQUETADORA': '__export__.mrp_workcenter_empaquetadora_termocontraible_dibipack_4255',
}

MAPEO_LAMINADO_PRODUCTOS_ODOO = {
    'LAMINADO MATE': '__export__.product_template_laminado_mate_gr_32_x_2000_cm',
    'LAMINADO BRILLO': '__export__.product_template_laminado_brillo_gr_32_x_2000_cm',
    'LAMINADO GOFRADO': '__export__.product_template_laminado_sosftouch_gr_32_x_150cm',
}

MAPEO_CATEGORIAS = {
    'PRODUCTOS_INTERMEDIOS': '__export__.product_category_XXXXXXXXX',
}

# ============================================================================
# MAPEOS PARA LOGICA DE NEGOCIO
# ============================================================================

ESTADOS_NO_CONFIRMABLES_IDS = [0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 33, 34, 36, 37, 38, 42, 44, 45, 48, 99]

# ============================================================================
# CONFIGURACIÓN DE FLUJO DE TRABAJO ODOO
# ============================================================================

PROJECT_NAME_PRE_PRODUCCION = "[Pre-Producción] Validación del Diseño del cliente"
TASK_STAGE_PARA_VALIDAR = "Para Validar"
TASK_STAGE_ESPERANDO_RESPUESTA = "Esperando Respuesta"

OPPORTUNITY_STAGE_ESPERANDO_RESPUESTA = "Esperando Respuesta"
OPPORTUNITY_STAGE_GANADO_SIN_OT = "Ganado sin OT"
OPPORTUNITY_STAGE_GANADO_CON_OT = "Ganado con OT"

ACTIVITY_SUMMARY_CONTACTAR_CLIENTE = "Contactar cliente para cerrar venta"
ACTIVITY_SUMMARY_RECLAMAR_ARCHIVOS = "Reclamar archivos"

# ============================================================================
# PARÁMETROS DE LOS SCRIPTS
# ============================================================================

BMG_SYNC_DAYS_BACK = 5
LOCAL_DB_STATUS_NO_APLICA = 'NO_APLICA'
LOCAL_DB_STATUS_LISTO_PARA_SINCRONIZAR = 'LISTO_PARA_SINCRONIZAR'
LOCAL_DB_STATUS_LISTADO = 'LISTADO'
BMG_ORDER_TYPE_EDIST = 'eDist'
BMG_PUBLISHER_FACILITY_LAD = 'LAD'

BMG_STATUS_ENTREGADO = 'ENTREGADO'
BMG_STATUS_FACTURADO = 'FACTURADO'
ODOO_ACTIVITY_TYPE_TODO = 'To Do'
ODOO_ACTIVITY_DEADLINE_DAYS = 1
TASK_NAME_PREFIX_VALIDACION_DISENO = 'Validación Diseño - '
TASK_DESCRIPTION_PREFIX_VALIDACION_DISENO = 'Validar diseño para '

ODOO_PARTNER_BIBLIOMANAGER = 'BIBLIOMANAGER'
BMG_ORDER_TYPE_EDIST_1_TO_1 = 'eDistrib. 1 a 1'
BMG_PUBLISHER_ID_PREFIX = 'EDIT'
BMG_TITLE_ID_PREFIX = 'PAP'
ODOO_OPPORTUNITY_NAME_PREFIX = 'Pedido BMG: '
ODOO_PRODUCT_SIZE_10_5X17 = "10.5x17"
ODOO_PRODUCT_SIZE_15_5X22_5 = "15.5x22.5"
ODOO_PRODUCT_SIZE_17X24 = "17x24"
ODOO_PRODUCT_SIZE_22X30 = "22x30"
ODOO_PRODUCT_SIZE_NO_CORRESPONDE = "No corresponde"
ODOO_CARRIER_ENVIO_SIN_COSTO = "Envío sin costo"
ODOO_CARRIER_ENVIO_BIBLIOTECA_SIN_COSTO = "Envío a biblioteca sin costo"
ODOO_TAX_VENTAS_EXENTOS_IVA = "Ventas Exentos IVA"
ODOO_TAX_VENTAS_IVA_22 = "IVA Ventas (22%)"
ODOO_TAX_ENTREGA_GRATUITA = "Entrega Gratuita"
ODOO_TAX_VENTAS_IVA_22_RATE = 22
ODOO_TAX_TYPE_SALE = "sale"
CURRENCY_USD = "USD"
CURRENCY_UYU = "UYU"
DISCOUNT_INTERNATIONAL_POD = 10.0
ODOO_SHIPPING_PRODUCT_NACIONAL = "Envío a cliente"
ODOO_SHIPPING_PRODUCT_EXTERIOR = "Envío a cliente en el exterior"
ODOO_PARTNER_RETIRA_IMPrenta = "Nesta Ltda., Retira en Imprenta"
ODOO_SHIPPING_METHOD_MERCADOENVIOS = "MercadoEnvíos"
ODOO_PICKING_TYPE_CODE_OUTGOING = 'outgoing'
ODOO_UOM_PRODUCT_UOM_UNIT_XMLID = 'uom.product_uom_unit'
ODOO_LOCATION_CUSTOMERS_XMLID = 'stock.stock_location_customers'
ODOO_SCHEDULED_TIME = "18:00:00"
ODOO_SHIPPING_NOTE_DEFAULT = "Sin observaciones."
EDIST_DELIVERY_RULES = { 0: 3, 1: 3, 2: 3, 3: 4, 4: 5, 5: 4, 6: 3 }
EDIST_DELIVERY_RULE_OVERRIDE_WEDNESDAY = 2
EDIST_DELIVERY_RULE_OVERRIDE_SATURDAY = 4
ODOO_CONTACT_DEFAULT_NAME = "Envio Desconocido"
ODOO_PARTNER_TYPE_DELIVERY = 'delivery'
BMG_ORDER_TYPE_POD = "POD"
BMG_ORDER_TYPE_EDIST_GENERIC = "eDist"
BMG_ORDER_CODE_PREFIX = "PED"
PRODUCT_ORIENTATION_VERTICAL = "Vertical"
PRODUCT_ORIENTATION_LANDSCAPE = "Apaisado"
PRODUCT_BLEED_YES = "Si"
PRODUCT_BLEED_NO = "No"
PRODUCT_SEALING_YES = "Con termosellado"
PRODUCT_SEALING_NO = "No termosellado"
PRODUCT_INK_BW = "1/1 negro"
CHATTER_MESSAGE_TYPE_COMMENT = 'comment'
CHATTER_SUBTYPE_XMLID_NOTE = 'mail.mt_note'


LOCAL_DB_STATUS_OF_CREADA = 'OF_CREADA'
ODOO_MRP_PRODUCTION_BMG_ORDER_LINE_FIELD = 'x_bmg_order_line'
ESTADOS_NO_CONFIRMABLES_PARA_OF = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 33, 34, 36, 37, 38, 42, 43, 44, 45, 48, 53, 99, 204, 205, 234]

FALLO_BUSQUEDA_NOTIFICAR_CADA_X_INTENTOS = 300
LOCAL_DB_STATUS_INTERIOR_PENDIENTE = 'PENDIENTE'
LOCAL_DB_STATUS_INTERIOR_GENERADO = 'GENERADO'
LOCAL_DB_STATUS_INTERIOR_FALLO_GENERACION = 'FALLO_GENERACION'
LOCAL_DB_STATUS_INTERIOR_FALLO_FATAL = 'FALLO_FATAL_INTERIOR'
GENERATED_FILE_TYPE_INTERIOR = 'interior'
GENERATED_FILE_TYPE_TAPA = 'tapa'

TAPA_PAPER_MAX_WIDTH_MM = 320
TAPA_FILENAME_TITLE_MAX_LENGTH = 50
LOCAL_DB_STATUS_TAPA_PENDIENTE = 'PENDIENTE'
LOCAL_DB_STATUS_TAPA_GENERADO = 'GENERADO'
LOCAL_DB_STATUS_TAPA_FALLO_GENERACION = 'FALLO_GENERACION'
LOCAL_DB_STATUS_TAPA_FALLO_FATAL = 'FALLO_FATAL_TAPA'

# --- CONFIGURACIÓN DE FUENTES Y CONVERSIÓN ---
FONT_PATH_LINUX_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_LINUX_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH_WINDOWS_REGULAR = "C:/Windows/Fonts/arial.ttf"
FONT_PATH_WINDOWS_BOLD = "C:/Windows/Fonts/arialbd.ttf"
BLEED_MM_DEFAULT = 3
MM_PER_POINT_CONVERSION = 25.4 / 72.0

# --- CONFIGURACIÓN DE MARCAS DE CORTE ---
CUT_MARK_OFFSET_MM = 5
CUT_MARK_LENGTH_MM = 5
CUT_MARK_COLOR_CMYK = (0, 0, 0, 1)
CUT_LINE_POSITION_INFERIOR = 'inferior'
CUT_LINE_POSITION_DERECHA = 'derecha'
CUT_LINE_POSITION_IZQUIERDA = 'izquierda'
CUT_LINE_POSITION_SUPERIOR = 'superior'

INK_COLOR_BW = "1/1 negro"
INK_COLOR_COLOR = "4/4 color"
BMG_COLOR_INSERT_YES = 'YES'
BMG_COVER_PRINTING_TYPE_CO40 = 'CO40'
BMG_FLAPS_WIDTH_NO = 'NO'

TAPA_LAMINATE_TEXT_Y_OFFSET = 28
TAPA_LAMINATE_TEXT_MIN_Y = 20
TAPA_LAMINATE_TEXT_FONTSIZE = 10
TAPA_LAMINATE_TEXT_COLOR = (0, 0, 0)
TAPA_PAPER_SIZE_33X36 = "33x36"
TAPA_PAPER_SIZE_33X48_7 = "33x48.7"
TAPA_PAPER_SIZE_33X70 = "33x70"

TAPA_PAPER_MAX_HEIGHT_33X36_MM = 350
TAPA_PAPER_MAX_HEIGHT_33X48_7_MM = 470
TAPA_PAPER_MAX_HEIGHT_33X70_MM = 690

# --- CONFIGURACIÓN DE ORDEN DE TRABAJO (OT) ---
OT_PAGE_SIZE = "A4"
OT_PAGE_MARGIN = 36 
OT_LINE_HEIGHT = 14
OT_FONT_BUILTIN_REGULAR = "helv"
OT_FONT_BUILTIN_BOLD = "helv-bold"

# ============================================================================
# CONFIGURACIÓN DE MERCADOLIBRE
# ============================================================================
ML_SINCRO_ACTIVADA = False
ML_FACTURACION_AUTOMATICA = False
MELI_CLIENT_ID = "2304119893923185"
MELI_CLIENT_SECRET = "HVEZWfIwMt5T8yYKghMbJVXTVe6N5jsY"
MELI_ACCESS_TOKEN = ""

# ============================================================================
# CONFIGURACIÓN DE DEPURACIÓN Y PRUEBAS
# ============================================================================
# Define un código de pedido específico para probar un único pedido en los scripts.
# Déjalo como "" o None para procesar todos los pedidos.
TEST_ORDER_CODE = ""
# ============================================================================
# --- FEATURE TOGGLES (Encendido/Apagado de módulos) ---
# ============================================================================
PRODUCCION_ACTIVADA = False       
PROCESAR_PDF_ACTIVADO = True     
NOTIFICAR_BMG_ACTIVADO = False    

# ============================================================================
# --- LÓGICA DE SOBREESCRITURA DE CONFIGURACIÓN ---
# ============================================================================
# Este bloque DEBE ir al final para que mapeos_local gane siempre.
try:
    from . import mapeos_local
    for key in dir(mapeos_local):
        if not key.startswith('__'):
            globals()[key] = getattr(mapeos_local, key)
    print("... Configuración local (mapeos_local.py) cargada. ...")
except ImportError:
    print("... Usando configuración de servidor (mapeos.py). ...")
