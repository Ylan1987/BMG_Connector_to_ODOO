"""
Archivo de configuración central para los mapeos.
Ambos scripts (procesador y sincronizador) importarán los
diccionarios desde aquí.
"""

# --- CONFIGURACION ODOO ---
DB_FILE = '/app/trabajos.db'
ODOO_URL = 'testkrl.odoo.imprentadiagonal.com.uy'
ODOO_DB = 'odoo17_stage'
ODOO_USUARIO = 'ylan.archimowicz@imprentadiagonal.com.uy'
ODOO_CONTRASENA = '77436602dbb10c3959d3cf28e12e0cf4d253f667'  # ¡¡¡IMPORTANTE: REEMPLAZA ESTO!!!
MERCADOLIBROS_CHANNEL_ID = '236' # ID de Canal para MercadoLibros

# --- NOMBRES DE PRODUCTOS EN ODOO ---
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

BLEED_MM = 3
MM_PER_POINT = 25.4 / 72.0

# --- CONFIGURACIÓN PRINCIPAL ---
WSDL_URL = 'http://wsbmg.bibliomanager.com/BGK20WS.asmx?WSDL'
FACILITY_ID = '128'
FACILITY_USER_ID = 'ylan'
PASSWORD = 'p4ssw0rdl4d'
BASE_STORAGE_PATH = r'/originales'
DEST_PATH_TAPAS = r'/salida/LAD/Tapas'
DEST_PATH_INTERIOR = r'/salida/LAD/Interior'
DB_FILE = '/app/trabajos.db'


MAPEO_NOMBRES_PAPEL = {
    "BNAHS070": "Ahuesado Ecologico 70", "BNAHS080": "Ahuesado Ecologico 80", "BNAHS090": "Ahuesado Ecologico 90", "BNAHU065": "Ahuesado 65" , "BNAHU070": "Ahuesado 70" , "BNAHU080": "Ahuesado 80" , "BNAHU090": "Ahuesado Ecologico 90", "BNAHU100": "Ahuesado 100" , "BNAHU125": "Ahuesado 125" , "BNAHV080": "Ahuesado 80" , "BNAHV090": "Ahuesado 90" , "BNAUT080": "Ahuesado 80" , "BNBIB045": "Obra 45", "BNCBD090": "Obra 90" , "BNCHA056": "Obra 56" , "BNCHA063": "Obra 63" , "BNCHA075": "Obra 75" , "BNCHA090": "Obra 90" , "BNCHA120": "Obra 120" , "BNCHA180": "Obra 180" , "BNCHA240": "Obra 240" , "BNCRE056": "Ahuesado 60" , "BNEAR070": "Ahuesado Ecologico 70", "BNEAR090": "Obra 80" , "BNHOL052": "Ahuesado 52" , "BNHOL055": "Ahuesado 55" , "BNILB090": "Coteado 90" , "BNILB115": "Coteado 115" , "BNILB125": "Coteado 130" , "BNILB135": "Coteado 130" , "BNILB150": "Coteado 150" , "BNILB170": "Coteado 170" , "BNILB230": "Coteado 230" , "BNILM080": "Coteado Mate 80" , "BNILM090": "Coteado Mate 90" , "BNILM115": "Coteado 115" , "BNILM125": "Coteado Mate 130" , "BNILM135": "Coteado Mate 130" , "BNILM150": "Coteado 150" , "BNILM170": "Coteado Mate 170" , "BNILM230": "Coteado Mate 230" , "BNNAT090": "Obra 90" , "BNNET100": "Obra 100" , "BNOBR040": "Obra 40" , "BNOBR050": "Obra 50" , "BNOBR056": "Obra 56" , "BNOBR060": "Obra 60" , "BNOBR063": "Obra 63" , "BNOBR070": "Obra 70" , "BNOBR075": "Obra 75" , "BNOBR080": "Obra 80" , "BNOBR090": "Obra 90" , "BNOBR100": "Obra 100" , "BNOBR110": "Obra 100" , "BNOBR120": "Obra 120" , "BNOBR130": "Obra 100" , "BNOBR150": "Obra 150" , "BNOPT050": "Obra 50" , "BNOPT075": "Obra 75" , "BNREC075": "Reciclado 75" , "BNREC100": "Reciclado 100" , "BNREC120": "Reciclado 120" , "BNREC240": "Reciclado 240" , "BNREG112": "Ahuesado 112" , "BNREG140": "Ahuesado 140" , "BNRLT090": "Reciclado 90" , "COAHS070": "Ahuesado Ecologico 70", "COAHS080": "Ahuesado Ecologico 80", "COAHS090": "Ahuesado Ecologico 90", "COAHU065": "Ahuesado 65" , "COAHU070": "Ahuesado 70" , "COAHU080": "Ahuesado 80" , "COAHU090": "Ahuesado Ecologico 90", "COAHU100": "Ahuesado 100" , "COAHU125": "Ahuesado 125" , "COAHV080": "Ahuesado 80" , "COAHV090": "Ahuesado 90" , "COAUT080": "Ahuesado 80" , "COBIB045": "Obra 45", "COCBD090": "Obra 90" , "COCHA056": "Obra 56" , "COCHA063": "Obra 63" , "COCHA075": "Obra 75" , "COCHA090": "Obra 90" , "COCHA120": "Obra 120" , "COCHA180": "Obra 180" , "COCHA240": "Obra 240" , "COCRE056": "Ahuesado 60" , "COEAR070": "Ahuesado Ecologico 70", "COEAR090": "Obra 80" , "COHOL052": "Ahuesado 52" , "COHOL055": "Ahuesado 55" , "COILB090": "Coteado 90" , "COILB115": "Coteado 115" , "COILB125": "Coteado 125" , "COILB135": "Coteado 135" , "COILB150": "Coteado 150" , "COILB170": "Coteado 170" , "COILB230": "Coteado 230" , "COILM080": "Coteado Mate 80" , "COILM090": "Coteado Mate 90" , "COILM115": "Coteado 115" , "COILM125": "Coteado Mate 125" , "COILM135": "Coteado Mate 135" , "COILM150": "Coteado 150" , "COILM170": "Coteado Mate 170" , "COILM230": "Coteado Mate 230" , "CONAT090": "Obra 90" , "CONET100": "Obra 100" , "COOBR040": "Obra 40" , "COOBR050": "Obra 50" , "COOBR056": "Obra 56" , "COOBR060": "Obra 60" , "COOBR063": "Obra 63" , "COOBR070": "Obra 70" , "COOBR075": "Obra 75" , "COOBR080": "Obra 80" , "COOBR090": "Obra 90" , "COOBR100": "Obra 100" , "COOBR110": "Obra 100" , "COOBR120": "Obra 120" , "COOBR130": "Obra 100" , "COOBR150": "Obra 150" , "COOPT050": "Obra 50" , "COOPT075": "Obra 75" , "COREC075": "Reciclado 75" , "COREC100": "Reciclado 100" , "COREC120": "Reciclado 120" , "COREC240": "Reciclado 240" , "COREG112": "Ahuesado 112" , "COREG140": "Ahuesado 140" , "CORLT090": "Reciclado 90" , "COAHU115": "Ahuesado 115" , "COAUT150": "Adhesivo 150", "COEAR70": "Ahuesado Ecologico 80", "COEAR90": "Obra 80" , "COINS150": "Coteado 150" , "CONER100": "Obra 100" , "CONNAT090": "Obra 100" , "COOBR180": "Obra 180" , "COOBR240": "Obra 240" , "-- Sin tapa --": "Sin Tapa", "TACAP250": "Cartulina 270" , "TACAR240": "Cartulina 270" , "TACAR300": "Cartulina 270" , "TACHA180": "Cartulina 270" , "TACONS280": "Cartulina 270" , "TADUCAR": "Tapa Dura", "TAhuesado Ecologico AR200": "Cartulina 270" , "TAhuesado Ecologico SM250": "Cartulina 270" , "TAhuesado Ecologico SM280": "Cartulina 270" , "TAhuesado Ecologico SM320": "Cartulina 270" , "TAILB115": "Coteado 115" , "TAILB150": "Coteado 150" , "TAILB170": "Coteado 170" , "TAILB230": "Coteado 230" , "TAILB300": "Cartulina 270" , "TAILM115": "Coteado Mate 115" , "TAILM150": "Coteado Mate 150" , "TAILM170": "Coteado Mate 170" , "TAILM230": "Coteado Mate 230" , "TAILM250": "Coteado Mate 250" , "TAILU200": "Coteado Mate 200" , "TAILU250": "Coteado Mate 250" , "TAILU270": "Cartulina 270" , "TAILU350": "Cartulina 270" , "TAMOD260": "Cartulina 270" , "TAOBR180": "Cartulina 270" , "TAOBR240": "Cartulina 270" , "TAORO300": "Cartulina 270" , "TAREC240": "Reciclado 240" , "TAREC300": "Reciclado 240" , "TAREV270": "Cartulina 270" , "TARLT250": "Cartulina 270" , "TASBS220": "Cartulina 270" , "TASBS250": "Cartulina 270" , "TASBS270": "Cartulina 270" , "TASBS280": "Cartulina 270" , "TATEX012": "Cartulina 270" , "TATEX014": "Cartulina 270" , "TATINCAM": "Cartulina 270" , "TATINCEY": "Cartulina 270" , "TAVER300B": "Cartulina 270" , "TAVER300C": "Cartulina 270" , "TAVER300N": "Cartulina 270" 
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

# 5. --- ¡NUEVO! CONFIGURACIÓN DE EMAIL ---
# Rellena estos datos con los de tu servidor de correo
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USUARIO = 'diagonalimprenta@gmail.com'
SMTP_CONTRASENA = 'sofalzjoktlqhsqo'
EMAIL_DESTINO = 'info@imprentadiagonal.com.uy'

# ============================================================================
# MAPEOS PARA SISTEMA DE FABRICACIÓN DINÁMICA
# ============================================================================

# --- CENTROS DE TRABAJO ---
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



# --- PRODUCTOS DE LAMINADO ---
# En metros lineales, ancho 32cm (lo que importa es el largo: 36, 48.7 o 70 cm)
MAPEO_LAMINADO_PRODUCTOS_ODOO = {
    'LAMINADO MATE': '__export__.product_template_laminado_mate_gr_32_x_2000_cm',
    'LAMINADO BRILLO': '__export__.product_template_laminado_brillo_gr_32_x_2000_cm',
    'LAMINADO GOFRADO': '__export__.product_template_laminado_sosftouch_gr_32_x_150cm',
}

# --- CATEGORÍAS DE PRODUCTOS ---
MAPEO_CATEGORIAS = {
    'PRODUCTOS_INTERMEDIOS': '__export__.product_category_XXXXXXXXX',  # ← COMPLETAR: Categoría para Interior/Tapa/Insert intermedios
}


