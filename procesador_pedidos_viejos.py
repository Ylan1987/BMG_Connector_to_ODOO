# -*- coding: utf-8 -*-

# --- IMPORTACIONES ---
import json
import sqlite3
import os
import re
from datetime import datetime
import math
from zeep import Client
from datetime import datetime, timedelta
import fitz  # PyMuPDF
import pypdf
import smtplib
from email.mime.text import MIMEText
from mapeos import WSDL_URL, FACILITY_ID, FACILITY_USER_ID, PASSWORD, BASE_STORAGE_PATH, DEST_PATH_TAPAS, DEST_PATH_INTERIOR, DB_FILE, MAPEO_NOMBRES_PAPEL, MAPEO_PAPEL
from mapeos import SMTP_SERVER, SMTP_PORT, SMTP_USUARIO, SMTP_CONTRASENA, EMAIL_DESTINO,BLEED_MM,MM_PER_POINT

LIMITE_DE_PRUEBA = 0
PEDIDO_DE_PRUEBA_ESPECIFICO = "" #ejemplo "PED00601532"

# --- CONFIGURACIÓN DE ALERTAS ---
INTENTOS_PARA_ERROR_FATAL = 900 #aprox 3 días
INTERVALO_EMAIL_ALERTA = 100 # Enviar un email cada 100 intentos fallido, aprox 8 horas

# --- FONT CONFIGURATION FOR WORK ORDER ---
# Ensure these paths are correct for your system.
# For Linux, DejaVuSans is common. For Windows, you might use Arial.ttf, etc.
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Fallback for Windows or if DejaVu is not found
if not os.path.exists(FONT_REGULAR_PATH) or not os.path.exists(FONT_BOLD_PATH):
    print("WARNING: DejaVuSans fonts not found at expected Linux path. Attempting to use generic system fonts.")
    if os.name == 'nt': # Windows
        FONT_REGULAR_PATH = "C:/Windows/Fonts/arial.ttf"
        FONT_BOLD_PATH = "C:/Windows/Fonts/arialbd.ttf"
    if not os.path.exists(FONT_REGULAR_PATH) or not os.path.exists(FONT_BOLD_PATH):
        print("ERROR: Generic system fonts not found. Work order generation might fail.")

BLEED_PTS = BLEED_MM / MM_PER_POINT

def inicializar_db():
    """
    Inicializa la DB. Crea la tabla si no existe y añade las columnas
    necesarias si faltan, para asegurar compatibilidad.
    """
    # Se asume que DB_FILE está disponible en este ámbito
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trabajos (
            order_code TEXT NOT NULL, line_number INTEGER NOT NULL, estado TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
            intentos_fallidos INTEGER DEFAULT 0, publisher_facility TEXT, publisher_id TEXT, title_id TEXT,
            ruta_archivo_tapa TEXT, ruta_archivo_contenido TEXT, order_date TEXT, client_reference TEXT,
            business_unit TEXT, publisher_name TEXT, order_type TEXT, run TEXT, line_status TEXT, code TEXT,
            title TEXT, line_status_date TEXT, delivery_date TEXT, quantity_requested INTEGER, total_pages INTEGER,
            height REAL, width REAL, bleed REAL, spine REAL, weight REAL, bw_paper_type TEXT, cover_paper_type TEXT,
            laminate TEXT, binding TEXT, datos_envio_json TEXT, publisher_observations TEXT, cover_printing_type TEXT,
            color_insert TEXT, color_pages TEXT, flaps_code TEXT, flaps_width TEXT, color_paper_type TEXT,
            PRIMARY KEY (order_code, line_number)
        )
    ''')

    cursor.execute("PRAGMA table_info(trabajos)")
    columnas_existentes = [row[1] for row in cursor.fetchall()]

    # ====================================================================
    # --- DICCIONARIO DE COLUMNAS ACTUALIZADO ---
    # Se han añadido todos los campos de precio y envío discutidos.
    # ====================================================================
    columnas_deseadas = {
        # --- COLUMNAS DE ODOO/ESTADO ---
        'estado_odoo': "TEXT DEFAULT 'PENDIENTE'",
        'odoo_opportunity_id': 'INTEGER',
        'odoo_sale_order_id': 'INTEGER',
        'channel': 'TEXT',
        'billing_number': 'TEXT',
        'bw_pages': 'INTEGER',
        'sealing': 'TEXT',
        'printing_facility': 'TEXT',
        'line_status_id': 'INTEGER',
        'odoo_product_variant_id': 'INTEGER', # <-- NUEVA COLUMNA
        'descripcion_detalle_libro': 'TEXT',
        'estado_fabricacion': "TEXT DEFAULT 'PENDIENTE'",
        'odoo_mrp_order_id': 'INTEGER',
        'odoo_sale_order_name': 'TEXT',
        'odoo_procurement_group_id': 'INTEGER',
        
        # --- DATOS DE FABRICACIÓN PRE-CALCULADOS ---
        'papel_tapa_size': 'TEXT',        # Ej: '33x48.7'
        'interior_layout': 'TEXT',        # Ej: '1up' o '2up'
        'interior_papel_folder': 'TEXT',  # Ej: '23x32'
        'copias_calculadas': 'INTEGER',

        # --- NUEVAS COLUMNAS DE PRECIO Y CAMBIO ---
        'unit_price': 'REAL',
        'unit_price_adjustment': 'REAL',
        'unit_currency': 'TEXT',
        'unit_currency_exchange': 'REAL',
        'unit_price_invoice': 'REAL',
        'unit_price_channel': 'REAL',
        'additional_services': 'REAL',
        'usd_exchange': 'REAL',
        
        # --- NUEVAS COLUMNAS DE ENVÍO A NIVEL DE ORDEN ---
        'shipping_cost_order': 'REAL',
        'shipping_cost_order_adjustment': 'REAL',
        'shipping_cost_currency': 'TEXT',
        'shipping_cost_instruction': 'REAL', # Para guardar el costo de la instrucción si es necesario
    }
    
    # --------------------------------------------------------------------

    for nombre_col, tipo_col in columnas_deseadas.items():
        if nombre_col not in columnas_existentes:
            print(f"🔧 Añadiendo columna faltante '{nombre_col}' a la base de datos...")
            cursor.execute(f"ALTER TABLE trabajos ADD COLUMN {nombre_col} {tipo_col}")
    
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada y actualizada con el esquema correcto.")

# REEMPLAZA ESTA FUNCIÓN
# REEMPLAZA TU FUNCIÓN ACTUAL CON ESTA VERSIÓN COMPLETA
def sincronizar_linea_con_db(order_element, line_element):
    def get_text(element, tag):
        if element is None: return ''
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ''

    attributes = line_element.find('Attributes')
    
    # 🚨 CAMPOS DE PRECIO DE LÍNEA Y GENERALES (NUEVOS)
    usd_exchange_rate = get_text(line_element, 'USDExchange')
    
    datos = {
        "order_code": get_text(line_element, 'OrderCode'), "line_number": get_text(line_element, 'LineNumber'),
        "fecha_actualizacion": datetime.now().isoformat(), "publisher_facility": get_text(order_element, 'PublisherFacility'),
        "publisher_id": get_text(order_element, 'PublisherId'), "title_id": get_text(line_element, 'TitleId'),
        "order_date": get_text(order_element, 'OrderDate'), "client_reference": get_text(order_element, 'ClientReference'),
        "business_unit": get_text(order_element, 'BusinessUnit'), "publisher_name": get_text(order_element, 'PublisherName'),
        "order_type": get_text(order_element, 'OrderType'), "run": get_text(line_element, 'Run'),
        "line_status": get_text(line_element, 'LineStatus'),
        "line_status_id": get_text(line_element, 'LineStatusId'),
        "odoo_sale_order_name": get_text(order_element, 'ClientReference'),
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
        
        # --- CAMPOS DE PRECIO DE LÍNEA (CLAVE) ---
        "unit_price": get_text(line_element, 'UnitPrice'),
        "unit_price_adjustment": get_text(line_element, 'UnitPriceAdjustment'),
        "unit_currency": get_text(line_element, 'UnitCurrency'),
        "unit_currency_exchange": get_text(line_element, 'UnitCurrencyExchange'),
        "unit_price_invoice": get_text(line_element, 'UnitPriceInvoice'),
        "unit_price_channel": get_text(line_element, 'UnitPriceChannel'),
        "additional_services": get_text(line_element, 'AdditionalServices'),
        "usd_exchange": usd_exchange_rate if usd_exchange_rate else get_text(order_element, 'USDExchange'),
        
        # --- CAMPOS DE ENVÍO A NIVEL DE ORDEN ---
        "shipping_cost_order": get_text(order_element, 'ShippingCost'),
        "shipping_cost_order_adjustment": get_text(order_element, 'ShippingCostAdjustment'),
        "shipping_cost_currency": get_text(order_element, 'ShippingCostCurrency'),
        
        # --- OTROS CAMPOS ---
        "channel": get_text(order_element, 'Channel'),
        "billing_number": get_text(order_element, 'BillingNumber'),
        "bw_pages": get_text(attributes, 'BWPages'),
        "sealing": get_text(attributes, 'Sealing'),
        "printing_facility": get_text(order_element, 'PrintingFacility')
    }

    # Procesamiento de Instrucciones de Envío (ShippingInstruction)
    shipping_instructions = []
    for instruction in order_element.findall('ShippingInstruction'):
        dest_info = {
            "InstructionLine": get_text(instruction, 'InstructionLine'), # CLAVE para distinguir múltiples envíos
            "Tipo_Envio": get_text(instruction, 'ShippingType'),
            "Operador": get_text(instruction, 'Operator'),
            "Empresa": get_text(instruction, 'Company'),
            "Destino": get_text(instruction, 'DestinationName'),
            "Direccion": get_text(instruction, 'Address'),
            "Ciudad": get_text(instruction, 'City'),
            "ZIPCode": get_text(instruction, 'ZIPCode'),
            "State": get_text(instruction, 'State'),
            "Country": get_text(instruction, 'Country'),
            "Telefono": get_text(instruction, 'Phone'),
            "Contacto": get_text(instruction, 'Contact'),
            "Email": get_text(instruction, 'DestinationEmail'),
            "Costo_Envio": get_text(instruction, 'ShippingCost'), # Costo por instrucción
            "ShippingCurrency": get_text(instruction, 'ShippingCurrency'),
            "TotalShippingCopies": get_text(instruction, 'TotalShippingCopies'),
            "Titulos": []
        }
        
        # Añade la información de los títulos dentro de esta instrucción de envío
        titles_to_send = instruction.find('TitlesToSend')
        if titles_to_send is not None:
            for title in titles_to_send.findall('Titles'):
                # Solo registra el título si coincide con la línea de pedido actual (oc_text / datos['code'])
                dest_info["Titulos"].append({
                    "TitleId": get_text(title, 'TitleId'),
                    "Title": get_text(title, 'Title'),
                    "Copies": get_text(title, 'Copies'),
                    "TotalWeight": get_text(title, 'TotalWeight') # <--- DEBE EXISTIR ESTA LÍNEA
                })
                
        shipping_instructions.append(dest_info)
    
    datos['datos_envio_json'] = json.dumps(shipping_instructions, ensure_ascii=False)
    # --- FIN DEL CAMBIO CLAVE ---

    # Lógica para decidir el estado de Odoo
    order_type_xml = get_text(order_element, 'OrderType')
    printing_facility_number_xml = get_text(order_element, 'PrintingFacilityNumber')
    publisher_facility_xml = get_text(order_element, 'PublisherFacility')
    estado_odoo_inicial = 'NO_APLICA'
    es_edist = 'eDist' in order_type_xml
    es_pod = not es_edist
    if (es_edist and printing_facility_number_xml == '128') or \
       (es_pod and (printing_facility_number_xml == '128' or publisher_facility_xml == 'LAD')):
        estado_odoo_inicial = 'LISTO_PARA_SINCRONIZAR'
    datos['estado_odoo'] = estado_odoo_inicial

    # Guardado en base de datos
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    try:
        columnas = ', '.join(datos.keys())
        placeholders = ', '.join(['?']*len(datos))
        # Para INSERT: Añadimos 'estado' y luego las claves de 'datos'
        cursor.execute(f"INSERT INTO trabajos (estado, {columnas}) VALUES ('LISTADO', {placeholders})", list(datos.values()))
    except sqlite3.IntegrityError:
        # Para UPDATE: Actualizamos todas las columnas de 'datos'
        update_clause = ', '.join([f"{key} = ?" for key in datos.keys()])
        cursor.execute(f"UPDATE trabajos SET {update_clause} WHERE order_code = ? AND line_number = ?", list(datos.values()) + [datos['order_code'], datos['line_number']])
    conn.commit()
    conn.close()

def enviar_email(asunto, cuerpo):
    print(f"      - Intentando enviar email: {asunto}")
    try:
        msg = MIMEText(cuerpo)
        msg['Subject'] = f"[AUTOMATIZACIÓN IMPRENTA] {asunto}"
        msg['From'] = SMTP_USUARIO
        msg['To'] = EMAIL_DESTINO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USUARIO, SMTP_CONTRASENA)
            server.send_message(msg)
        print("      - Email enviado con éxito.")
    except Exception as e:
        print(f"      - ERROR: No se pudo enviar el email. {e}")


def actualizar_estado_y_reintentos(oc, ln, nuevo_estado, incrementar_error=False):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    trabajo_actual = obtener_linea_para_procesar(oc, ln) # Re-usamos para obtener estado actual
    intentos = trabajo_actual.get('intentos_fallidos', 0)

    if incrementar_error:
        intentos += 1
        # Alerta por email cada X intentos, sin incluir el intento fatal
        if (intentos % INTERVALO_EMAIL_ALERTA == 0) and intentos > 0 and intentos < INTENTOS_PARA_ERROR_FATAL:
            enviar_email(f"Alerta de Reintentos ({intentos})", f"El pedido {oc}-{ln} ('{trabajo_actual.get('title')}') ha fallado {intentos} veces.\nÚltimo estado de error: {nuevo_estado}")
        
        # Error fatal al alcanzar el umbral
        if intentos >= INTENTOS_PARA_ERROR_FATAL:
            enviar_email("ERROR FATAL en Pedido", f"El pedido {oc}-{ln} ('{trabajo_actual.get('title')}') ha fallado {intentos} veces.\nSe ha marcado como ERROR_FATAL.\nÚltimo estado de error: {nuevo_estado}")
            nuevo_estado = 'ERROR_FATAL'
    
    cursor.execute("UPDATE trabajos SET estado = ?, intentos_fallidos = ?, fecha_actualizacion = ? WHERE order_code = ? AND line_number = ?", 
                   (nuevo_estado, intentos, datetime.now().isoformat(), oc, ln))
    conn.commit()
    conn.close()
    print(f"  => Estado actualizado a '{nuevo_estado}' para {oc} - Línea {ln} (Intentos: {intentos})")

def actualizar_rutas_archivos(oc, ln, ruta_tapa, ruta_contenido):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute("UPDATE trabajos SET ruta_archivo_tapa = ?, ruta_archivo_contenido = ? WHERE order_code = ? AND line_number = ?", (ruta_tapa, ruta_contenido, oc, ln))
    conn.commit()
    conn.close()

def actualizar_datos_fabricacion(oc, ln, papel_tapa_size, interior_layout, interior_papel_folder, copias_calculadas):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE trabajos
        SET papel_tapa_size = ?, interior_layout = ?, interior_papel_folder = ?, copias_calculadas = ?
        WHERE order_code = ? AND line_number = ?
    """, (papel_tapa_size, interior_layout, interior_papel_folder, copias_calculadas, oc, ln))
    conn.commit()
    conn.close()
    print(f"  => Datos de fabricación guardados para {oc} - Línea {ln}")

def actualizar_estado_fabricacion(oc, ln, nuevo_estado):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute("UPDATE trabajos SET estado_fabricacion = ? WHERE order_code = ? AND line_number = ?", (nuevo_estado, oc, ln))
    conn.commit()
    conn.close()
    print(f"  => Estado de fabricación actualizado a '{nuevo_estado}' para {oc} - Línea {ln}")


def obtener_linea_para_procesar(oc, ln):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trabajos WHERE order_code = ? AND line_number = ?", (oc, ln))
    fila = cursor.fetchone()
    conn.close()
    return dict(fila) if fila else None

def limpiar_id(id_original, prefijo):
    if not id_original: return None
    id_sin_prefijo = id_original[len(prefijo):] if id_original.startswith(prefijo) else id_original
    return id_sin_prefijo.lstrip('0')

def obtener_cajas_normalizadas_pypdf(ruta_archivo):
    """
    Usa pypdf para leer las coordenadas de las cajas (Media, Trim, Bleed).
    Aplica la normalización (traslación) para que MediaBox.x0/y0 = 0.
    
    Devuelve un diccionario con las cajas como fitz.Rect.
    """
    print(f"      [DEBUG PyPDF] Procesando archivo: {os.path.basename(ruta_archivo)}")
    try:
        with open(ruta_archivo, 'rb') as file:
            reader = pypdf.PdfReader(file)
            page = reader.pages[0]
            
            coords_pypdf = {
                'media': page.mediabox,
                'trim': page.get('/TrimBox'),
                'bleed': page.get('/BleedBox')
            }

            print(f"      [DEBUG PyPDF] Cajas leídas (sin normalizar):")
            print(f"        MediaBox: {coords_pypdf['media']}")
            print(f"        TrimBox: {coords_pypdf['trim']}")
            print(f"        BleedBox: {coords_pypdf['bleed']}")

            if coords_pypdf['trim'] is None:
                print("      [DEBUG PyPDF] ADVERTENCIA: page.get('/TrimBox') devolvió None.")

            # 1. Calcular el Vector de Traslación (T)
            media_x0, media_y0, _, _ = coords_pypdf['media']
            vector_tx = -float(media_x0)
            vector_ty = -float(media_y0)
            
            cajas_fitz_normalizadas = {}

            # 2. Convertir a fitz.Rect y aplicar la traslación
            for name, coords in coords_pypdf.items():
                if coords is not None:
                    x0, y0, x1, y1 = [float(c) for c in coords]
                    
                    # Aplica la traslación para normalizar el origen a (0, 0)
                    caja_normalizada = fitz.Rect(x0 + vector_tx, y0 + vector_ty, x1 + vector_tx, y1 + vector_ty)
                    
                    cajas_fitz_normalizadas[name] = caja_normalizada

            print(f"      [DEBUG PyPDF] Cajas normalizadas (fitz.Rect):")
            print(f"        MediaBox: {cajas_fitz_normalizadas.get('media')}")
            print(f"        TrimBox: {cajas_fitz_normalizadas.get('trim')}")
            print(f"        BleedBox: {cajas_fitz_normalizadas.get('bleed')}")

            return cajas_fitz_normalizadas

    except Exception as e:
        print(f"❌ ERROR en la lectura de PyPDF: {e}")
        return None

def encontrar_ruta_trabajo_dinamicamente(base_path, publisher_ids_limpios, title_id_limpio):
    """
    Busca un directorio de trabajo que coincida con title_id_limpio y cuyo
    directorio padre coincida con ALGUNO de los publisher_ids_limpios, en la profundidad correcta.
    """
    print(f"    Buscando dinámicamente por TitleID: '{title_id_limpio}' y PublisherIDs: '{publisher_ids_limpios}' en '{base_path}'")
    base_path = os.path.normpath(base_path)
    for root, dirs, files in os.walk(base_path):
        # No procesar el directorio base
        if os.path.normpath(root) == base_path:
            depth = 0
        else:
            relative_path = os.path.normpath(root).replace(base_path, '')
            # Quitar la barra inicial si existe
            if relative_path.startswith(os.sep):
                relative_path = relative_path[1:]
            depth = len(relative_path.split(os.sep))

        if depth == 3 and title_id_limpio in dirs:
            # Potencial coincidencia encontrada. Ahora verificamos el directorio padre.
            parent_dir_name = os.path.basename(root)
            print(f"      [DEBUG RUTA] Encontrado '{title_id_limpio}' en '{root}'. Carpeta padre: '{parent_dir_name}'.")

            if parent_dir_name in publisher_ids_limpios:
                full_path = os.path.join(root, title_id_limpio)
                print(f"      - ¡Ruta encontrada y validada!: {full_path}")
                print(f"        (Coincide TitleID: '{title_id_limpio}' y el PublisherID padre '{parent_dir_name}' está en la lista permitida)")
                return full_path # Ruta válida encontrada, podemos detener la búsqueda.
            else:
                # Coincidencia de title_id, pero el publisher es incorrecto. Continuamos buscando.
                print(f"      [DEBUG RUTA] TitleID '{title_id_limpio}' encontrado, pero PublisherID padre '{parent_dir_name}' no está en la lista permitida. Continuando búsqueda...")
                continue # Continuar con la siguiente iteración de os.walk

    print(f"      - ERROR: No se encontró ninguna ruta que coincida con TitleID '{title_id_limpio}' y cuya carpeta padre esté en la lista de PublisherIDs permitidos.")
    return None

import os
import re
from datetime import datetime
# Nota: La función asume que tienes 'fitz' y 're' importados.

def encontrar_archivo_mas_reciente(directorio, title_id_limpio, tipo_archivo, order_type):
    """
    Busca el archivo de contenido o tapa más reciente basado en el tipo de orden (MODO ESTRICTO):
    - eDistrib. 1 a 1: Busca el archivo MASTER MÁS RECIENTE del tipo solicitado (TAPA o CONTENIDO).
    - POD/Normal: Busca el archivo *_BN_... más reciente y chequea coherencia contra TODOS los archivos del directorio.
    """
    archivos_aptos = []        # Candidatos válidos para imposición (archivos *_BN_ para POD)
    archivos_coherencia = []   # Candidatos válidos (archivos MASTER para eDist)
    archivos_totales = []      # TODOS los archivos para modo POD (check de coherencia)
    
    # --- DETECCIÓN DE MODO DE OPERACIÓN ---
    es_edist = order_type == 'eDistrib. 1 a 1' # Verificación estricta
    
    # 1. LISTA DE EXCLUSIÓN Y PATRONES
    # Claves específicas para la búsqueda (se usa para identificar el tipo de MASTER en modo eDist)
    PATRON_MASTER_GENERAL = r"MASTER"
    PATRON_TAPA = r"(COVER|TAPA)"
    PATRON_CONTENIDO = r"(CONTENT|CONTENIDO|INTERIOR)"


    # Claves que identifican archivos de coherencia amplia (usado en modo POD para la verificación de fechas)
    PALABRAS_CLAVE_COHERENCIA_POD = r"(MASTER|ORIGINAL|BACKUP|COMPROBACION|PRUEBA|MUESTRA|TRIMBOX|IMPO|MASTER_LOW|ORIGINAL_LOW)" 
    PATRON_EXCLUSION_COHERENCIA = r"(IMPO)" 
    PATRON_CONTENIDO_GENERAL = r"(CONTENT|CONTENIDO|INTERIOR|BN)"
    PATRON_TAPA_GENERAL = r"(COVER|TAPA)"
    # Patrón que busca el sufijo de versión *_BN_..._\d.pdf (APTO para POD)
    if tipo_archivo == 'CONTENIDO':
        patron_apto_pod = re.compile(f"^{re.escape(title_id_limpio)}_CONTENIDO_BN.*_(\\d+)\\.pdf$", re.IGNORECASE)
        patron_master_tipo = re.compile(PATRON_CONTENIDO, re.IGNORECASE) # Patrón para validar tipo en eDist
        patron_tipo_a_filtrar = re.compile(PATRON_CONTENIDO_GENERAL, re.IGNORECASE)
    elif tipo_archivo == 'TAPA':
        patron_apto_pod = re.compile(f"^{re.escape(title_id_limpio)}_TAPA.*_(\\d+)\\.pdf$", re.IGNORECASE)
        patron_master_tipo = re.compile(PATRON_TAPA, re.IGNORECASE) # Patrón para validar tipo en eDist
        patron_tipo_a_filtrar = re.compile(PATRON_TAPA_GENERAL, re.IGNORECASE)
    else:
        return None 
        
    patron_coherencia_pod = re.compile(PALABRAS_CLAVE_COHERENCIA_POD, re.IGNORECASE)
    patron_exclusion = re.compile(PATRON_EXCLUSION_COHERENCIA, re.IGNORECASE) 
    try:
        archivos_en_directorio = os.listdir(directorio)
        
        # 2. CLASIFICAR CANDIDATOS SEGÚN EL MODO
        for nombre_archivo in archivos_en_directorio:
            ruta_completa = os.path.join(directorio, nombre_archivo)
            
            try:
                fecha_modificacion = os.path.getmtime(ruta_completa)
            except OSError:
                continue 
            
            # Recopilamos todos los archivos para el chequeo POD
            if not es_edist:
                if patron_tipo_a_filtrar.search(nombre_archivo):
                    # 🚨 CORRECCIÓN: SOLO añadir a archivos_totales si NO es un archivo de exclusión (IMPO).
                    if not patron_exclusion.search(nombre_archivo): 
                        archivos_totales.append({'fecha': fecha_modificacion, 'ruta': ruta_completa, 'nombre': nombre_archivo})
            # Detección de coincidencias
            es_master_general = re.search(PATRON_MASTER_GENERAL, nombre_archivo, re.IGNORECASE)
            coincidencia_apta_pod = patron_apto_pod.match(nombre_archivo)

            # --- LÓGICA DE CLASIFICACIÓN ESTRICTA ---
            if es_edist:
                # MODO EDIST: SOLO archivos MASTER Y del TIPO correcto son candidatos válidos (archivos_coherencia)
                es_tipo_correcto = patron_master_tipo.search(nombre_archivo)
                
                if es_master_general and es_tipo_correcto: # <-- ¡FILTRO DOBLE CLAVE!
                    archivos_coherencia.append({'fecha': fecha_modificacion, 'ruta': ruta_completa, 'nombre': nombre_archivo})
            
            else: # MODO POD/NORMAL
                # MODO POD: SOLO los *_BN_ son candidatos válidos (archivos_aptos)
                if coincidencia_apta_pod:
                    version_num = int(coincidencia_apta_pod.group(1))
                    archivos_aptos.append({'version': version_num, 'fecha': fecha_modificacion, 'ruta': ruta_completa, 'nombre': nombre_archivo})
            # --- FIN LÓGICA DE CLASIFICACIÓN ESTRICTA ---


        # 3. IDENTIFICAR EL MEJOR ARCHIVO APTO Y REALIZAR EL CHEQUEO

        if es_edist:
            # 3A. MODO EDIST: Seleccionamos el último MASTER que exista.
            if not archivos_coherencia:
                print(f"  ⚠️ ERROR: No se encontraron archivos MASTER del tipo '{tipo_archivo}' para pedido EDIST.")
                return None
            
            # Elegimos el archivo MASTER más reciente por fecha
            mejor_apto = max(archivos_coherencia, key=lambda x: x['fecha']) 

        else: # MODO POD/NORMAL
            # 3B. MODO POD: Seleccionamos el último *_BN_ que exista.
            if not archivos_aptos:
                print(f"  ⚠️ ERROR: No se encontraron archivos *_BN_ para pedido POD.")
                return None

            # Elegimos el *_BN_ más reciente por (fecha, versión)
            mejor_apto = max(archivos_aptos, key=lambda x: (x['fecha'], x['version']))
            ultima_fecha_apta = mejor_apto['fecha']
            
            # 4. VERIFICAR COHERENCIA (Contra TODOS los archivos del directorio)
            if archivos_totales:
                # Buscamos la fecha de modificación MÁS RECIENTE de CUALQUIER archivo
                ultima_fecha_total = max(archivos_totales, key=lambda x: x['fecha'])['fecha']
                
                # REGLA CLAVE POD: Si CUALQUIER archivo es más reciente que el *_BN_ seleccionado
                if ultima_fecha_total > ultima_fecha_apta:
                    fecha_total_dt = datetime.fromtimestamp(ultima_fecha_total).strftime('%Y-%m-%d %H:%M:%S')
                    fecha_apta_dt = datetime.fromtimestamp(ultima_fecha_apta).strftime('%Y-%m-%d %H:%M:%S')
                    
                    print(f"  ❌ ALERTA DE CLIENTE (POD): Archivo general MÁS RECIENTE.")
                    print(f"    Archivo más reciente: {fecha_total_dt}")
                    print(f"    Apto seleccionado (*_BN_): {os.path.basename(mejor_apto['ruta'])} ({fecha_apta_dt})")
                    print(f"    => Se requiere validación. Proceso detenido.")
                    return None # Detener el proceso por inconsistencia


        # 5. RETORNO EXITOSO
        print(f"  ✅ Archivo final seleccionado: {os.path.basename(mejor_apto['ruta'])}")
        return mejor_apto['ruta']
        
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  ❌ ERROR CRÍTICO durante la búsqueda de archivos: {e}")
        return None

def procesar_tapa(trabajo_actual):
    print("    Procesando TAPA...")
    ruta_original = trabajo_actual['ruta_archivo_tapa']
    print(f"      -> Abriendo el archivo original: '{os.path.basename(ruta_original)}'")

    try:
        # 1. Abrimos el documento original con fitz para manipulación
        doc = fitz.open(ruta_original)
        
        if doc.page_count == 0:
            print("      ERROR: El PDF de la tapa está vacío (0 páginas).")
            doc.close()
            return None, None
        
        # 2. Obtenemos las cajas normalizadas usando pypdf
        cajas_normalizadas = obtener_cajas_normalizadas_pypdf(ruta_original)
        if not cajas_normalizadas or 'trim' not in cajas_normalizadas:
            print("      ERROR: No se pudo obtener el TrimBox normalizado para la tapa.")
            doc.close()
            return None, None
        
        trim_box = cajas_normalizadas['trim'] # Usamos el TrimBox normalizado
        page = doc[0] # Obtenemos la primera página para modificarla
        
        # 3. Añadimos el texto del laminado 1cm (28 puntos) por encima del bleedbox
        laminado = trabajo_actual.get('laminate')
        if laminado:
            posicion_x = trim_box.x0
            posicion_y = trim_box.y0 - 28
            if posicion_y < 20: # Nos aseguramos de que no se salga de la página
                posicion_y = 20
            page.insert_text(fitz.Point(posicion_x, posicion_y), f"Laminado: {laminado}", fontsize=10, color=(0, 0, 0))

        final_width_pts = trim_box.width + (2 * BLEED_PTS)
        final_height_pts = trim_box.height + (2 * BLEED_PTS)

        final_width_mm, final_height_mm = final_width_pts * MM_PER_POINT, final_height_pts * MM_PER_POINT
        
        papel_size_str = ""
        if (final_width_mm <= 320 and final_height_mm <= 350) or (final_width_mm <= 350 and final_height_mm <= 320): papel_size_str = "33x36"
        elif (final_width_mm <= 320 and final_height_mm <= 470) or (final_width_mm <= 470 and final_height_mm <= 320): papel_size_str = "33x48.7" # Corregido el tamaño del pliego
        elif (final_width_mm <= 320 and final_height_mm <= 690) or (final_width_mm <= 690 and final_height_mm <= 320): papel_size_str = "33x70"
        else:
             print(f"      ERROR: Tamaño requerido ({final_width_mm:.1f}x{final_height_mm:.1f} mm) excede máximo de pliego 33x70."); doc.close(); return None, None
        oc_limpio = limpiar_id(trabajo_actual['order_code'], 'PED')
        titulo_saneado = re.sub(r'[\\/*?:"<>|]', "", trabajo_actual['title'])
        nuevo_nombre = f"{oc_limpio}-{trabajo_actual['line_number']}_{papel_size_str}x{trabajo_actual['quantity_requested']}_{titulo_saneado[:50]}.pdf"
        
        # 4. Guardamos el documento MODIFICADO con el nuevo nombre
        os.makedirs(DEST_PATH_TAPAS, exist_ok=True)
        ruta_destino = os.path.join(DEST_PATH_TAPAS, nuevo_nombre)
        
        doc.save(ruta_destino)
        doc.close()

        print(f"      - Tapa guardada en: {os.path.basename(ruta_destino)}")
        return ruta_destino, papel_size_str

    except Exception as e:
        print(f"      ERROR: No se pudo procesar el archivo PDF de la tapa: {e}")
        return None, None

# AÑADE ESTA NUEVA FUNCIÓN AUXILIAR (puedes ponerla antes de 'procesar_interior')
# REEMPLAZA ESTA FUNCIÓN COMPLETA
# REEMPLAZA ESTA FUNCIÓN COMPLETA
# REEMPLAZA ESTA FUNCIÓN COMPLETA
def dibujar_lineas_de_corte(page, trim_box, posicion):
    """
    Dibuja las marcas de corte alrededor de un TrimBox, a 5mm de distancia.
    La lógica se basa en la posición de la página para omitir las marcas
    correctas en el medianil de una imposición, según la regla especificada.
    """
    offset = 14.17  # 5 mm en puntos
    longitud_marca = 14.17
    color_corte = (0, 0, 0, 1)  # CMYK Negro de Registro
    x0, y0, x1, y1 = trim_box

    # --- Esquina SUPERIOR-IZQUIERDA ---
    # Marca Vertical Superior (en x0, y0)
    if posicion != 'inferior':
        page.draw_line(fitz.Point(x0, y0 - offset), fitz.Point(x0, y0 - offset - longitud_marca), color=color_corte, width=0.25)
    # Marca Horizontal Izquierda (en x0, y0)
    if posicion != 'derecha':
        page.draw_line(fitz.Point(x0 - offset, y0), fitz.Point(x0 - offset - longitud_marca, y0), color=color_corte, width=0.25)

    # --- Esquina SUPERIOR-DERECHA ---
    # Marca Vertical Superior (en x1, y0)
    if posicion != 'inferior':
        page.draw_line(fitz.Point(x1, y0 - offset), fitz.Point(x1, y0 - offset - longitud_marca), color=color_corte, width=0.25)
    # Marca Horizontal Derecha (en x1, y0)
    if posicion != 'izquierda':
        page.draw_line(fitz.Point(x1 + offset, y0), fitz.Point(x1 + offset + longitud_marca, y0), color=color_corte, width=0.25)

    # --- Esquina INFERIOR-IZQUIERDA ---
    # Marca Vertical Inferior (en x0, y1)
    if posicion != 'superior':
        page.draw_line(fitz.Point(x0, y1 + offset), fitz.Point(x0, y1 + offset + longitud_marca), color=color_corte, width=0.25)
    # Marca Horizontal Izquierda (en x0, y1)
    if posicion != 'derecha':
        page.draw_line(fitz.Point(x0 - offset, y1), fitz.Point(x0 - offset - longitud_marca, y1), color=color_corte, width=0.25)

    # --- Esquina INFERIOR-DERECHA ---
    # Marca Vertical Inferior (en x1, y1)
    if posicion != 'superior':
        page.draw_line(fitz.Point(x1, y1 + offset), fitz.Point(x1, y1 + offset + longitud_marca), color=color_corte, width=0.25)
    # Marca Horizontal Derecha (en x1, y1)
    if posicion != 'izquierda':
        page.draw_line(fitz.Point(x1 + offset, y1), fitz.Point(x1 + offset + longitud_marca, y1), color=color_corte, width=0.25)


def marcar_cajas_en_original(ruta_original, cajas_a_marcar, papel_folder):
    """
    Abre el PDF original, dibuja múltiples rectángulos con colores especificados 
    y lo guarda en la carpeta de destino de la impresora correspondiente.
    
    :param cajas_a_marcar: Lista de tuplas (fitz.Rect, str color_nombre)
    """
    print(f"    🎨 Marcando múltiples cajas en el PDF original: '{os.path.basename(ruta_original)}'")
    
    # Mapeo de colores (CMYK a RGB para fitz)
    MAPEO_COLORES = {
        "celeste": (0, 1, 1),    # Cian
        "amarillo": (1, 1, 0),   # Amarillo
        "rojo": (1, 0, 0)        # Magenta/Rojo
    }
    
    # 1. Crear el nuevo nombre de archivo (sufijo único para el PDF marcado)
    directorio, nombre_archivo_ext = os.path.split(ruta_original)
    nombre_base, extension = os.path.splitext(nombre_archivo_ext)
    nuevo_nombre = f"{nombre_base}_MARCADO{extension}"

    # 2. Definir la ruta de destino (Ricoh 8310 y el papel correspondiente)
    DEST_PATH_BASE = os.path.join(DEST_PATH_INTERIOR, "Ricoh 8310", papel_folder)
    os.makedirs(DEST_PATH_BASE, exist_ok=True)
    ruta_destino = os.path.join(DEST_PATH_BASE, nuevo_nombre)
    
    try:
        doc = fitz.open(ruta_original)
        
        # 3. Iterar sobre todas las páginas y dibujar todos los rectángulos
        for i in range(len(doc)):
            page = doc[i]
            
            for caja, color_nombre in cajas_a_marcar:
                color_rgb = MAPEO_COLORES.get(color_nombre.lower(), (0, 0, 0))
                
                # --- CAMBIO CLAVE: Aumentar el ancho (width) y usar línea sólida (dashes=[]) ---
                page.draw_rect(caja, 
                               color=color_rgb, 
                               width=1.5,      # Aumento de 0.5 a 1.5 para que sea más notable
                               dashes=[],      # Línea sólida para máxima visibilidad
                               overlay=True)
            
        # 4. Guardar el nuevo documento
        doc.save(ruta_destino, garbage=3, clean=True)
        doc.close()
        print(f"    ✅ PDF original MARCADO con 3 cajas guardado en: '{ruta_destino.replace(DEST_PATH_INTERIOR, '...')}'")
        return ruta_destino
        
    except Exception as e:
        print(f"    ❌ ERROR al marcar las cajas en el PDF original: {e}")
        return None

# REEMPLAZA ESTA FUNCIÓN COMPLETA
def procesar_interior(trabajo_actual):
    doc_orden_trabajo = crear_pagina_orden_de_trabajo(trabajo_actual)
    if not doc_orden_trabajo:
        print("    ERROR: Se canceló el procesamiento del interior porque no se pudo generar la orden de trabajo.")
        return None, None, None, None
    print("    Procesando INTERIOR...")
    ruta_original = trabajo_actual['ruta_archivo_contenido']
    print(f"    -> Intentando abrir el archivo de interior en: '{ruta_original}'")
    try:
        doc = fitz.open(ruta_original)
    except Exception as e:
        print(f"    ERROR: No se pudo abrir o leer el archivo PDF del interior: {e}")
        return None, None, None, None
    if doc.page_count == 0:
        print(f"    ERROR: El PDF del interior está vacío o corrupto (0 páginas).")
        doc.close(); return None, None, None, None
    
    cantidad = int(trabajo_actual['quantity_requested'])
    
    cajas_normalizadas = obtener_cajas_normalizadas_pypdf(ruta_original)

    caja_de_recorte_pdf_original = None
    has_bleed_api = float(trabajo_actual.get('bleed', 0)) > 0

    # --- LÓGICA DE SELECCIÓN DE CAJA REESTRUCTURADA ---
    # Primero, se intenta la lógica del MediaBox si no hay sangrado.
    if not has_bleed_api:
        print("    - API indica sin sangrado. Intentando validar MediaBox...")
        caja_media_normalizada = cajas_normalizadas.get('media')
        width_mm_meta = float(trabajo_actual.get('width', 0))
        height_mm_meta = float(trabajo_actual.get('height', 0))

        if caja_media_normalizada and caja_media_normalizada.width > 0:
            media_width_mm = round(caja_media_normalizada.width * MM_PER_POINT, 2)
            media_height_mm = round(caja_media_normalizada.height * MM_PER_POINT, 2)

            if abs(media_width_mm - width_mm_meta) <= 1 and abs(media_height_mm - height_mm_meta) <= 1:
                caja_de_recorte_pdf_original = caja_media_normalizada
                print("    ✅ MediaBox validado contra metadatos. Se usará como caja base.")
            else:
                print(f"    - MediaBox ({media_width_mm:.1f}x{media_height_mm:.1f}mm) no coincide con metadatos ({width_mm_meta:.1f}x{height_mm_meta:.1f}mm). Pasando a lógica de TrimBox.")
        else:
            print("    - No se encontró MediaBox válido. Pasando a lógica de TrimBox.")

    # Si la caja aún no se ha definido (porque hay sangrado, o porque el MediaBox falló),
    # se aplica la lógica de TrimBox como principal o fallback.
    if caja_de_recorte_pdf_original is None:
        print("    - Aplicando lógica de TrimBox...")
        if 'trim' in cajas_normalizadas and cajas_normalizadas['trim'].width > 0:
            caja_de_recorte_pdf_original = cajas_normalizadas['trim']
            print("    ✅ TrimBox encontrado y se usará como caja base.")
        else:
            print("    ❌ ERROR CRÍTICO: No se pudo determinar una caja base válida (ni MediaBox validado, ni TrimBox encontrado).")
            doc.close(); return None, None, None, None

    if caja_de_recorte_pdf_original is None:
        print("    ❌ ERROR CRÍTICO: Fallo inesperado en la lógica de selección de caja.")
        doc.close(); return None, None, None, None
        
    # =======================================================================
    # --- FIN LÓGICA DE CAJA BASE ---
    # =======================================================================

    # --- 2. DETERMINACIÓN DE SANGRADO Y CÁLCULO DE CAJAS CON SANGRADO ---
    has_bleed = False
    try:
        # Usamos el BLEED_MM global para la lógica
        if float(trabajo_actual.get('bleed', 0)) > 0:
            has_bleed = True
    except (ValueError, TypeError):
        has_bleed = False

    if has_bleed:
        print("    - Se detectó sangrado. Agrandando el TrimBox en 3mm.")
        # `caja_de_calculo_final` es el área del PDF original que incluye el sangrado (TrimBox + 2*BLEED_PTS)
        caja_de_calculo_final = fitz.Rect(caja_de_recorte_pdf_original.x0 - BLEED_PTS, caja_de_recorte_pdf_original.y0 - BLEED_PTS,
                                                 caja_de_recorte_pdf_original.x1 + BLEED_PTS, caja_de_recorte_pdf_original.y1 + BLEED_PTS)
    else:
        print("    - No se detectó sangrado. Usando el TrimBox.")
        # Si no hay sangrado, el área a recortar es simplemente el TrimBox
        caja_de_calculo_final = caja_de_recorte_pdf_original

    print(f"    🎯 Caja base del libro (TrimBox/MediaBox): {caja_de_recorte_pdf_original.x0:.2f}, {caja_de_recorte_pdf_original.y0:.2f}, {caja_de_recorte_pdf_original.x1:.2f}, {caja_de_recorte_pdf_original.y1:.2f}")
    print(f"    🎯 Área de recorte del PDF original (Clip): {caja_de_calculo_final.x0:.2f}, {caja_de_calculo_final.y0:.2f}, {caja_de_calculo_final.x1:.2f}, {caja_de_calculo_final.y1:.2f}")
    
    width_mm = round(caja_de_recorte_pdf_original.width * MM_PER_POINT, 2)
    height_mm = round(caja_de_recorte_pdf_original.height * MM_PER_POINT, 2)
    orientacion = 'V' if height_mm >= width_mm else 'A'
    print(f"    - Orientación detectada: {'Vertical' if orientacion == 'V' else 'Apaisado'}")
    print(f"    - Dimensiones calculadas (mm): Ancho={width_mm:.2f}, Alto={height_mm:.2f}")

    layout, papel_folder = ("1up", "23x32")
    if orientacion == 'V':
        if (width_mm <= 156 and height_mm <= 221): layout, papel_folder = ("2up", "23x32")
        elif (width_mm <= 171 and height_mm <= 241): layout, papel_folder = ("2up", "25x35")
    elif orientacion == 'A':
        if (width_mm <= 221 and (height_mm * 2) <= 312):
            layout, papel_folder = ("2up", "23x32")
    
    print(f"    - DECISIÓN FINAL: Layout='{layout}', Papel='{papel_folder}'")

    oc_limpio = limpiar_id(trabajo_actual['order_code'], 'PED')
    papel_resumido = MAPEO_PAPEL.get(trabajo_actual['bw_paper_type'], "N_A")
    copias = math.ceil(cantidad / 2) if layout == "2up" and (cantidad % 2 == 0 or cantidad >= 10) else cantidad
    nuevo_nombre = f"{oc_limpio}-{trabajo_actual['line_number']}_{papel_resumido}x{copias}_{orientacion}.pdf"

    imposed_doc = fitz.open()
    papel_dims_cm = [int(d) for d in papel_folder.split('x')]
    
    if layout == "1up":
        papel_w_pts, papel_h_pts = (papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT # Pliego en puntos

        # Determinar el tamaño del contenido a colocar en el pliego (TrimBox + sangrado si existe)
        content_width_on_sheet = caja_de_recorte_pdf_original.width
        content_height_on_sheet = caja_de_recorte_pdf_original.height

        if has_bleed:
            content_width_on_sheet += (2 * BLEED_PTS)
            content_height_on_sheet += (2 * BLEED_PTS)

        for i in range(len(doc)):
            new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
            
            # Calcular offset para centrar el contenido (TrimBox + sangrado si existe)
            x_offset = (papel_w_pts - content_width_on_sheet) / 2
            y_offset = (papel_h_pts - content_height_on_sheet) / 2
            
            # Rectángulo en el pliego donde se colocará el arte (incluyendo sangrado)
            target_rect_artwork = fitz.Rect(x_offset, y_offset, x_offset + content_width_on_sheet, y_offset + content_height_on_sheet)
            
            # El clip es siempre el área de arte del PDF original (TrimBox + sangrado)
            new_page.show_pdf_page(target_rect_artwork, doc, i, clip=caja_de_calculo_final)
            
            # El TrimBox para dibujar las marcas de corte es el tamaño real del libro (TrimBox)
            # ajustado a su posición en el pliego.
            trimbox_for_marks = fitz.Rect(target_rect_artwork)
            if has_bleed:
                trimbox_for_marks.x0 += BLEED_PTS
                trimbox_for_marks.y0 += BLEED_PTS
                trimbox_for_marks.x1 -= BLEED_PTS
                trimbox_for_marks.y1 -= BLEED_PTS
            
            dibujar_lineas_de_corte(new_page, trimbox_for_marks, 'unica')
            
    elif layout == "2up":
        # Papel siempre apaisado para 2up vertical (se asume que el pliego se gira si es necesario)
        papel_w_pts, papel_h_pts = max((papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT), \
                                   min((papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT)

        W_trim = caja_de_recorte_pdf_original.width
        H_trim = caja_de_recorte_pdf_original.height

        imposed_block_width = (2 * W_trim) + (2 * BLEED_PTS if has_bleed else 0)
        imposed_block_height = H_trim + (2 * BLEED_PTS if has_bleed else 0)
        
        margen_vertical = (papel_h_pts - imposed_block_height) / 2
        margen_lateral = (papel_w_pts - imposed_block_width) / 2

        trim_rect_izq_on_sheet = fitz.Rect(
            margen_lateral + (BLEED_PTS if has_bleed else 0),
            margen_vertical + (BLEED_PTS if has_bleed else 0),
            margen_lateral + (BLEED_PTS if has_bleed else 0) + W_trim,
            margen_vertical + (BLEED_PTS if has_bleed else 0) + H_trim
        )
        trim_rect_der_on_sheet = fitz.Rect(
            trim_rect_izq_on_sheet.x1,
            trim_rect_izq_on_sheet.y0,
            trim_rect_izq_on_sheet.x1 + W_trim,
            trim_rect_izq_on_sheet.y1
        )

        target_rect_izq = fitz.Rect(
            trim_rect_izq_on_sheet.x0 - (BLEED_PTS if has_bleed else 0),
            trim_rect_izq_on_sheet.y0 - (BLEED_PTS if has_bleed else 0),
            trim_rect_izq_on_sheet.x1,
            trim_rect_izq_on_sheet.y1 + (BLEED_PTS if has_bleed else 0)
        )
        target_rect_der = fitz.Rect(
            trim_rect_der_on_sheet.x0,
            trim_rect_der_on_sheet.y0 - (BLEED_PTS if has_bleed else 0),
            trim_rect_der_on_sheet.x1 + (BLEED_PTS if has_bleed else 0),
            trim_rect_der_on_sheet.y1 + (BLEED_PTS if has_bleed else 0)
        )

        def get_clip_for_page(page_index):
            """Devuelve el clip correcto (con sangrado) para una página par o impar."""
            clip = fitz.Rect(caja_de_recorte_pdf_original)
            if not has_bleed:
                return clip
            
            # Página impar (1, 3, ...), índice par (0, 2, ...)
            if (page_index + 1) % 2 != 0: 
                clip.x1 += BLEED_PTS # Sangrado a la derecha
            # Página par (2, 4, ...), índice impar (1, 3, ...)
            else:
                clip.x0 -= BLEED_PTS # Sangrado a la izquierda
            
            clip.y0 -= BLEED_PTS # Sangrado superior
            clip.y1 += BLEED_PTS # Sangrado inferior
            return clip

        # --- LÓGICA DE IMPOSICIÓN: PARTIDO vs. CABEZA-CON-CABEZA ---
        if cantidad <= 9 and cantidad % 2 != 0:
            # MODO PARTIDO (Cut and Stack)
            print("    - Imponiendo en modo 'Partido' (Cut and Stack)...")
            total_pages_inicial = len(doc)
            paginas_a_anadir = (4 - total_pages_inicial % 4) % 4
            if paginas_a_anadir > 0:
                print(f"    - Añadiendo {paginas_a_anadir} pág. en blanco para llegar a múltiplo de 4.")
                for _ in range(paginas_a_anadir):
                    doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
            
            total_pages = len(doc)
            h = total_pages // 2
            for i in range(h):
                new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
                p1_idx, p2_idx = i, i + h

                clip1 = get_clip_for_page(p1_idx)
                clip2 = get_clip_for_page(p2_idx)

                # Hoja impuesta impar (1, 3, 5...)
                if (i + 1) % 2 != 0:
                    new_page.show_pdf_page(target_rect_izq, doc, p1_idx, rotate=180, clip=clip1)
                    new_page.show_pdf_page(target_rect_der, doc, p2_idx, rotate=0, clip=clip2)
                # Hoja impuesta par (2, 4, 6...)
                else:
                    new_page.show_pdf_page(target_rect_izq, doc, p2_idx, rotate=0, clip=clip2)
                    new_page.show_pdf_page(target_rect_der, doc, p1_idx, rotate=180, clip=clip1)
                
                dibujar_lineas_de_corte(new_page, trim_rect_izq_on_sheet, 'izquierda')
                dibujar_lineas_de_corte(new_page, trim_rect_der_on_sheet, 'derecha')

        else:
            # MODO CABEZA CON CABEZA
            print("    - Imponiendo en modo 'Cabeza con Cabeza'...")
            total_pages = len(doc)
            for i in range(total_pages):
                new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
                clip = get_clip_for_page(i)

                # Página original impar (1, 3, 5...)
                if (i + 1) % 2 != 0:
                    new_page.show_pdf_page(target_rect_izq, doc, i, rotate=180, clip=clip)
                    new_page.show_pdf_page(target_rect_der, doc, i, rotate=0, clip=clip)
                # Página original par (2, 4, 6...)
                else:
                    new_page.show_pdf_page(target_rect_izq, doc, i, rotate=0, clip=clip)
                    new_page.show_pdf_page(target_rect_der, doc, i, rotate=180, clip=clip)

                dibujar_lineas_de_corte(new_page, trim_rect_izq_on_sheet, 'izquierda')
                dibujar_lineas_de_corte(new_page, trim_rect_der_on_sheet, 'derecha')
    
    doc.close()

    # --- PASO FINAL: Añadir la orden de trabajo al principio ---
    print("    - Añadiendo hoja de orden de trabajo al PDF impuesto...")
    imposed_doc.insert_pdf(doc_orden_trabajo, start_at=0)

    rutas_guardadas = []
    rutas_destino_base = []
    if cantidad < 10:
        rutas_destino_base.append(os.path.join(DEST_PATH_INTERIOR, "Ricoh 8310", papel_folder))
    else:
        rutas_destino_base.append(os.path.join(DEST_PATH_INTERIOR, "Ricoh 8310", papel_folder))
        rutas_destino_base.append(os.path.join(DEST_PATH_INTERIOR, "Ricoh 8420", papel_folder))

    for ruta in rutas_destino_base:
        os.makedirs(ruta, exist_ok=True)
        ruta_final = os.path.join(ruta, nuevo_nombre)
        imposed_doc.save(ruta_final)
        print(f"    - Interior guardado en: {ruta_final.replace(DEST_PATH_INTERIOR, '...')}")
        rutas_guardadas.append(ruta_final)
    
    imposed_doc.close()

    return rutas_guardadas, layout, papel_folder, copias

def procesar_pedidos():
    codigos_a_procesar = set()
    print(f"--- Iniciando Proceso de Pedidos [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    try:
        cliente_wsdl = Client(WSDL_URL)
        print("Conexión a API establecida.")
        fecha_final_str = datetime.now().strftime('%Y%m%d')
        fecha_inicial_str = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        order_data_element = cliente_wsdl.service.BMBillingInterface(FacilityID=FACILITY_ID, FacilityUserId=FACILITY_USER_ID, Password=PASSWORD, FromDate=fecha_inicial_str, ToDate=fecha_final_str)
        if order_data_element is not None:
            pedidos = order_data_element.findall('Order')
            if pedidos:
                nuevos_codigos = {p.find('OrderCode').text for p in pedidos if p.find('OrderCode') is not None}
                codigos_a_procesar.update(nuevos_codigos)
        print(f"Se encontraron {len(codigos_a_procesar)} pedidos nuevos/recientes en la API.")
    except Exception as e:
        print(f"Error al obtener la lista de pedidos de la API: {e}")
    

    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        query_pendientes = """
            SELECT DISTINCT order_code 
            FROM trabajos 
            WHERE 
                -- Condición original: Reintentar si hubo error en ESTE script
                (estado NOT IN ('IMPUESTO', 'ENVIADO_A_IMPRESORA', 'ERROR_FATAL'))
                OR -- Añadir esta condición: O si Odoo lo dejó pendiente
                (estado_odoo = 'PENDIENTE_DE_CONFIRMAR') 
        """ # <-- AHORA TAMBIÉN MIRA EL ESTADO DE ODOO
        cursor.execute(query_pendientes)
        pedidos_con_error = cursor.fetchall()
        conn.close()
        if pedidos_con_error:
            codigos_error = {row[0] for row in pedidos_con_error}
            print(f"Se encontraron {len(codigos_error)} pedidos con errores para reintentar.")
            codigos_a_procesar.update(codigos_error)
    except Exception as e:
        print(f"Error al buscar pedidos con error en la DB: {e}")

    print(f"Total de pedidos únicos a procesar (Nuevos + Errores): {len(codigos_a_procesar)}") 

    if not codigos_a_procesar:
        print("No hay pedidos nuevos ni con errores para procesar.")
        print("\n--- Proceso Finalizado ---")
        return


    if PEDIDO_DE_PRUEBA_ESPECIFICO:
        print(f"--- MODO DE PRUEBA ESPECÍFICO: Procesando solo el pedido {PEDIDO_DE_PRUEBA_ESPECIFICO} ---")
        codigos_a_procesar = {PEDIDO_DE_PRUEBA_ESPECIFICO}
    elif LIMITE_DE_PRUEBA > 0 and len(codigos_a_procesar) > 0:
        print(f"--- MODO DE PRUEBA ACTIVO: Procesando solo {min(LIMITE_DE_PRUEBA, len(codigos_a_procesar))} de {len(codigos_a_procesar)} pedidos ---")
        codigos_a_procesar = set(list(codigos_a_procesar)[:LIMITE_DE_PRUEBA])
    
    for code in list(codigos_a_procesar):
        try:
            resultado_detalle = cliente_wsdl.service.BMBillingByOrder(OrderCode=code, FacilityUserId=FACILITY_USER_ID, Password=PASSWORD)
            
            if resultado_detalle is None: continue
            order_element = resultado_detalle.find('Order')
            if order_element is None: continue

            # --- INICIO DE LA LÓGICA CORREGIDA ---
            # 1. Extraer TODOS los publisher IDs del pedido y limpiarlos.
            all_publisher_id_tags = order_element.findall('PublisherId')
            publisher_ids_limpios = list(set([limpiar_id(tag.text, 'EDIT') for tag in all_publisher_id_tags if tag.text]))
            print(f"  - IDs de Publisher encontrados para el pedido {code}: {publisher_ids_limpios}")
            # --- FIN DE LA LÓGICA CORREGIDA ---

            lineas = order_element.findall('Orderline')
            if not lineas: continue

            for linea_element in lineas:
                oc_text = linea_element.find('OrderCode').text if linea_element.find('OrderCode') is not None else None
                ln_text = linea_element.find('LineNumber').text if linea_element.find('LineNumber') is not None else None
                if not (oc_text and ln_text): continue
                oc, ln = oc_text, int(ln_text)
                
                sincronizar_linea_con_db(order_element, linea_element)
                trabajo_actual = obtener_linea_para_procesar(oc, ln)
                if not trabajo_actual: continue

                estado_actual = trabajo_actual['estado']
                if estado_actual == 'ENVIADO_A_IMPRESORA': continue
                

                if estado_actual == 'LISTADO':
                    print(f"  - Procesando {oc} - Línea {ln} (Estado actual: {estado_actual})")
                    actualizar_estado_y_reintentos(oc, ln, 'PROCESADO'); estado_actual = 'PROCESADO'
                
                if estado_actual in ['PROCESADO', 'ERROR_RUTA_NO_ENCONTRADA', 'ERROR_ARCHIVO_NO_ENCONTRADO', 'ERROR_IMPOSICION','ERROR_DATOS_INCOMPLETOS']:
                    print(f"  - Procesando {oc} - Línea {ln} (Estado actual: {estado_actual})")
                    
                    # --- INICIO DE LA LÓGICA CORREGIDA ---
                    # 2. Usar la lista de IDs para la búsqueda de ruta.
                    title_id_limpio = limpiar_id(trabajo_actual['title_id'], 'PAP')
                    order_type = trabajo_actual.get('order_type', '')
                    if not title_id_limpio:
                        actualizar_estado_y_reintentos(oc, ln, 'ERROR_DATOS_INCOMPLETOS', incrementar_error=True); continue

                    ruta_trabajo = encontrar_ruta_trabajo_dinamicamente(BASE_STORAGE_PATH, publisher_ids_limpios, title_id_limpio)
                    # --- FIN DE LA LÓGICA CORREGIDA ---

                    if ruta_trabajo:
                        ruta_contenido = encontrar_archivo_mas_reciente(ruta_trabajo, title_id_limpio, 'CONTENIDO', order_type)
                        ruta_tapa = encontrar_archivo_mas_reciente(ruta_trabajo, title_id_limpio, 'TAPA', order_type)
                        if ruta_contenido and ruta_tapa:
                            actualizar_rutas_archivos(oc, ln, ruta_tapa, ruta_contenido)
                            trabajo_actual['ruta_archivo_tapa'] = ruta_tapa
                            trabajo_actual['ruta_archivo_contenido'] = ruta_contenido
                            actualizar_estado_y_reintentos(oc, ln, 'ARCHIVO_ENCONTRADO'); estado_actual = 'ARCHIVO_ENCONTRADO'
                        else:
                            actualizar_estado_y_reintentos(oc, ln, 'ERROR_ARCHIVO_NO_ENCONTRADO', incrementar_error=True)
                    else:
                        actualizar_estado_y_reintentos(oc, ln, 'ERROR_RUTA_NO_ENCONTRADA', incrementar_error=True)

                
                if estado_actual == 'ARCHIVO_ENCONTRADO':
                    print(f"  - Procesando {oc} - Línea {ln} (Estado actual: {estado_actual})")
                    try:
                        ruta_tapa_procesada, papel_tapa_size = procesar_tapa(trabajo_actual)
                        rutas_interior_impuesto, interior_layout, interior_papel_folder, copias_calculadas = procesar_interior(trabajo_actual)
                        if ruta_tapa_procesada and rutas_interior_impuesto:
                            actualizar_datos_fabricacion(oc, ln, papel_tapa_size, interior_layout, interior_papel_folder, copias_calculadas)
                            actualizar_estado_y_reintentos(oc, ln, 'IMPUESTO'); estado_actual = 'IMPUESTO'
                            actualizar_estado_fabricacion(oc, ln, 'LISTO_PARA_FABRICAR')
                            print("    Trabajo impuesto. Listo para enviar a la impresora.")
                        else:
                            actualizar_estado_y_reintentos(oc, ln, 'ERROR_IMPOSICION', incrementar_error=True)
                    except Exception as e:
                        print(f"      ERROR CRÍTICO durante la imposición: {e}"); actualizar_estado_y_reintentos(oc, ln, 'ERROR_IMPOSICION', incrementar_error=True)

                if estado_actual == 'IMPUESTO':
                    #print("    Trabajo impuesto. Listo para enviar a la impresora.")
                    pass

        except Exception as e:
            print(f"  Error fatal procesando detalles del pedido {code}: {e}")
    
    print("\n--- Proceso Finalizado ---")

# REEMPLAZA ESTA FUNCIÓN COMPLETA
def crear_pagina_orden_de_trabajo(trabajo_actual):
    """Crea un nuevo documento PDF de una página A4 con la orden de trabajo."""
    print("      - Creando hoja de orden de trabajo...")
    try:
        # Definimos constantes para el layout y fuentes
        A4 = fitz.paper_size("a4")
        margen = 36
        line_height = 12

        use_builtin_fonts = False
        font_reg_id = None
        font_bold_id = None

        doc_ot = fitz.open()
        page = doc_ot.new_page(width=A4[0], height=A4[1])
        
        # --- Registrar fuentes para el documento ---
        try:
            if os.path.exists(FONT_REGULAR_PATH) and os.path.exists(FONT_BOLD_PATH):
                font_reg_id = page.insert_font(fontfile=FONT_REGULAR_PATH, fontname="F-Reg")
                font_bold_id = page.insert_font(fontfile=FONT_BOLD_PATH, fontname="F-Bold")
            else:
                raise FileNotFoundError("Custom font files not found.")
        except Exception as e:
            print(f"      WARNING: Fallback to built-in fonts. Error loading custom fonts: {e}")
            use_builtin_fonts = True

        # --- PARTE SUPERIOR: IMAGEN DE LA TAPA ---
        rect_img = fitz.Rect(margen, margen, A4[0] - margen, A4[1] / 2)
        ruta_tapa = trabajo_actual.get('ruta_archivo_tapa')
        if ruta_tapa and os.path.exists(ruta_tapa):
            try:
                with fitz.open(ruta_tapa) as doc_tapa:
                    if doc_tapa.page_count > 0:
                        pix_tapa = doc_tapa[0].get_pixmap()
                        page.insert_image(rect_img, pixmap=pix_tapa, keep_proportion=True)
            except Exception as e:
                print(f"      ADVERTENCIA: No se pudo insertar la imagen de la tapa. Error: {e}")

        # --- PARTE INFERIOR: TEXTO DE LA ORDEN DE TRABAJO ---
        y = A4[1] / 2 + 20

        rect_col_izq = fitz.Rect(margen, y, A4[0] / 2 - 10, A4[1] - margen)
        rect_col_der = fitz.Rect(A4[0] / 2 + 10, y, A4[0] - margen, A4[1] - margen)
        y_izq, y_der = y, y

        # --- FUNCIONES AUXILIARES CORREGIDAS ---
        # REEMPLAZA ESTA FUNCIÓN AUXILIAR
        def escribir_linea_izq(texto, es_titulo=False, indent=0):
            nonlocal y_izq
            rect = fitz.Rect(rect_col_izq.x0 + indent, y_izq, rect_col_izq.x1, y_izq + line_height)
            if use_builtin_fonts:
                fontname = "helv-bold" if es_titulo else "helv"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            else:
                fontname = "F-Bold" if es_titulo else "F-Reg"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            y_izq += line_height if not es_titulo else (line_height * 1.5)

        # REEMPLAZA ESTA OTRA FUNCIÓN AUXILIAR
        def escribir_linea_der(texto, es_titulo=False, indent=0):
            nonlocal y_der
            rect = fitz.Rect(rect_col_der.x0 + indent, y_der, rect_col_der.x1, y_der + line_height)
            if use_builtin_fonts:
                fontname = "helv-bold" if es_titulo else "helv"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            else:
                fontname = "F-Bold" if es_titulo else "F-Reg"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            y_der += line_height if not es_titulo else (line_height * 1.5)

        # --- Llenamos las columnas con los datos ---
        oc_limpio = limpiar_id(trabajo_actual.get('order_code', ''), 'PED')
        escribir_linea_izq("Libro", es_titulo=True)
        escribir_linea_izq(f"{trabajo_actual.get('title', 'N/A')} ({oc_limpio}-{trabajo_actual.get('line_number', '')})")
        escribir_linea_izq(f"Cantidad: {trabajo_actual.get('quantity_requested', 'N/A')}")
        escribir_linea_izq(f"Tamaño: {trabajo_actual.get('width', '0')} x {trabajo_actual.get('height', '0')} mm")
        escribir_linea_izq(f"Unidad de negocio: {trabajo_actual.get('business_unit', 'N/A')}")
        escribir_linea_izq(f"Tipo: {trabajo_actual.get('order_type', 'N/A')}")
        y_izq += line_height

        escribir_linea_izq("Interior", es_titulo=True)
        escribir_linea_izq(f"Páginas: {trabajo_actual.get('total_pages', 'N/A')}")
        papel_interior_code = trabajo_actual.get('bw_paper_type')
        texto_papel_interior = MAPEO_NOMBRES_PAPEL.get(papel_interior_code, papel_interior_code or 'N/A')
        escribir_linea_izq(f"Papel: {texto_papel_interior}")
        tintas_interior = "1/1 negro"
        if int(trabajo_actual.get('color_pages', 0)) > 0: tintas_interior = "4/4 color"
        escribir_linea_izq(f"Tintas: {tintas_interior}")
        escribir_linea_izq(f"Comentarios del cliente: {trabajo_actual.get('publisher_observations', '')}")
        y_izq += line_height
        
        if trabajo_actual.get('color_insert') == 'YES':
            escribir_linea_izq("Insertos color", es_titulo=True)
            escribir_linea_izq(f"Páginas: {trabajo_actual.get('color_pages', 'N/A')}")
            papel_color_code = trabajo_actual.get('color_paper_type')
            texto_papel_color = MAPEO_NOMBRES_PAPEL.get(papel_color_code, papel_color_code or 'N/A')
            escribir_linea_izq(f"Papel: {texto_papel_color}")
            y_izq += line_height
            
        escribir_linea_der("Tapas", es_titulo=True)
        escribir_linea_der(f"Lomo: {trabajo_actual.get('spine', '0')} mm")
        escribir_linea_der(f"Tintas: {'4/0' if trabajo_actual.get('cover_printing_type') == 'CO40' else 'N/A'}")
        papel_tapa_code = trabajo_actual.get('cover_paper_type')
        texto_papel_tapa = MAPEO_NOMBRES_PAPEL.get(papel_tapa_code, papel_tapa_code or 'N/A')
        escribir_linea_der(f"Papel: {texto_papel_tapa}")
        flaps_width = trabajo_actual.get('flaps_width', '0')
        escribir_linea_der(f"Solapas: {'NO' if str(flaps_width) == '0' else f'{flaps_width} mm'}")
        y_der += line_height

        escribir_linea_der("Terminaciones", es_titulo=True)
        escribir_linea_der(f"Encuadernado: {trabajo_actual.get('binding', 'N/A')}")
        escribir_linea_der(f"Laminado: {trabajo_actual.get('laminate', 'N/A')}")
        escribir_linea_der(f"Filial: {trabajo_actual.get('publisher_facility', 'N/A')}")
        y_der += line_height * 2

        datos_envio = json.loads(trabajo_actual.get('datos_envio_json', '[]'))
        for i, envio in enumerate(datos_envio, 1):
            escribir_linea_der(f"Envío {i}", es_titulo=True)
            for clave, valor in envio.items():
                if not valor or not str(valor).strip(): continue
                if clave == "Titulos":
                    if valor:
                        escribir_linea_der("#### Títulos a enviar")
                        for titulo_envio in valor:
                            escribir_linea_der(f"- {titulo_envio.get('Title', 'N/A')} ({titulo_envio.get('Copies', 0)} copias)", indent=10)
                else:
                    escribir_linea_der(f"{clave}: {valor}")
            y_der += line_height

        return doc_ot
        
    except Exception as e:
        print(f"      ERROR: No se pudo generar la orden de trabajo: {e}")
        return None

if __name__ == "__main__":
    if DB_FILE: os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    inicializar_db()
    procesar_pedidos()
