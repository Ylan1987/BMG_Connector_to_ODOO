import os
import re
import sqlite3
import fitz
import logging
from common import mapeos, db_conn, odoo_conn

# Configurar logging
_logger = logging.getLogger(__name__)

MM_PER_POINT = 25.4 / 72.0
BLEED_PTS = 3 / MM_PER_POINT

def limpiar_id(id_original, prefijo):
    if not id_original: return None
    id_sin_prefijo = id_original[len(prefijo):] if id_original.startswith(prefijo) else id_original
    return id_sin_prefijo.lstrip('0')

def obtener_cajas_normalizadas_pypdf(ruta_archivo):
    import pypdf
    try:
        with open(ruta_archivo, 'rb') as file:
            reader = pypdf.PdfReader(file)
            page = reader.pages[0]
            media = page.mediabox
            trim = page.get('/TrimBox') or media
            tx, ty = -float(media[0]), -float(media[1])
            return {
                'media': fitz.Rect(float(media[0])+tx, float(media[1])+ty, float(media[2])+tx, float(media[3])+ty),
                'trim': fitz.Rect(float(trim[0])+tx, float(trim[1])+ty, float(trim[2])+tx, float(trim[3])+ty)
            }
    except: return None

def encontrar_ruta_trabajo_dinamicamente(base_path, publisher_ids_limpios, title_id_limpio):
    pub_ids = []
    for pid in publisher_ids_limpios:
        if not pid: continue
        for p in str(pid).split(','):
            clean_p = p.replace('EDIT', '').strip().lstrip('0')
            if clean_p and clean_p not in pub_ids: pub_ids.append(clean_p)
    tid = str(title_id_limpio).replace('PAP', '').strip().lstrip('0')
    
    _logger.info(f"      -> Buscando ruta para TitleID: '{tid}' con Publisher IDs: {pub_ids}")
    _logger.info(f"      -> RUTA BASE A REVISAR: {base_path}")

    if not os.path.exists(base_path):
        _logger.warning(f"      -> ❌ Ruta base no encontrada: {base_path}")
        return None
    
    try:
        # Structure: base_path / Pais / Facility / Publisher / Title
        for pais_dir in os.listdir(base_path):
            pais_path = os.path.join(base_path, pais_dir)
            if not os.path.isdir(pais_path): continue
            
            _logger.info(f"      -> Revisando País: {pais_path}")
            for facility_dir in os.listdir(pais_path):
                facility_path = os.path.join(pais_path, facility_dir)
                if not os.path.isdir(facility_path): continue
                
                for pub_dir in os.listdir(facility_path):
                    current_pub_id = pub_dir.lstrip('0')
                    current_pub_id = pub_dir.lstrip('0').strip()
                    if current_pub_id in pub_ids:
                        pub_path = os.path.join(facility_path, pub_dir)
                        if not os.path.isdir(pub_path): continue

                        _logger.info(f"      -> Match de Publisher encontrado. Revisando carpeta: {pub_path}")
                        for title_dir in os.listdir(pub_path):
                            if title_dir.lstrip('0') == tid:
                                ruta = os.path.join(pub_path, title_dir)
                                _logger.info(f"      -> ✅ Carpeta encontrada: {ruta}")
                                return ruta
    except Exception as e:
        _logger.error(f"      -> ❌ Error buscando ruta dinámicamente: {e}")
        pass
    
    _logger.warning(f"      -> ⚠️ No se encontró la carpeta para TitleID: {tid} con los publishers provistos.")
    return None

def encontrar_archivo_mas_reciente(directorio, title_id_limpio, tipo_archivo, order_type):
    archivos_aptos = []; archivos_coherencia = []; archivos_totales = []
    es_edist = order_type == 'eDistrib. 1 a 1'
    PATRON_MASTER = r"MASTER"; PATRON_TAPA = r"(COVER|TAPA)"; PATRON_TAPA_GEN = r"(COVER|TAPA)"
    
    patron_apto_pod = re.compile(f"^{re.escape(title_id_limpio)}_TAPA.*_(\\d+)\\.pdf$", re.IGNORECASE)
    patron_master_tipo = re.compile(PATRON_TAPA, re.IGNORECASE)
    patron_tipo_gen = re.compile(PATRON_TAPA_GEN, re.IGNORECASE)
    patron_exclusion = re.compile(r"(IMPO)", re.IGNORECASE)

    try:
        for f in os.listdir(directorio):
            ruta = os.path.join(directorio, f)
            try: mtime = os.path.getmtime(ruta)
            except: continue
            if not es_edist and patron_tipo_gen.search(f) and not patron_exclusion.search(f):
                archivos_totales.append({'fecha': mtime, 'ruta': ruta, 'nombre': f})
            
            is_master = re.search(PATRON_MASTER, f, re.IGNORECASE)
            match_pod = patron_apto_pod.match(f)
            if es_edist and is_master and patron_master_tipo.search(f):
                archivos_coherencia.append({'fecha': mtime, 'ruta': ruta, 'nombre': f})
            elif not es_edist and match_pod:
                archivos_aptos.append({'version': int(match_pod.group(1)), 'fecha': mtime, 'ruta': ruta, 'nombre': f})

        if es_edist:
            if not archivos_coherencia: return None, "No se encontró un archivo MASTER de tapa."
            mejor = max(archivos_coherencia, key=lambda x: x['fecha'])
            return mejor['ruta'], None
        else:
            if not archivos_aptos: return None, "No se encontró un archivo validado (*_TAPA_..._X.pdf)."
            mejor = max(archivos_aptos, key=lambda x: (x['fecha'], x['version']))
            if archivos_totales:
                posterior = max(archivos_totales, key=lambda x: x['fecha'])
                if posterior['fecha'] > mejor['fecha']:
                    msg = f"Se encontró un archivo posterior al validado: `{posterior['nombre']}`. Por favor, corregir el error en el NAS para procesar el validado que tenga la fecha más reciente."
                    return None, msg
            return mejor['ruta'], None
    except: return None, "Error al listar el directorio en el NAS."

def procesar_tapa(trabajo_actual):
    oc = trabajo_actual.get('order_code')
    ln = trabajo_actual.get('line_number')
    tid = trabajo_actual.get('title_id')
    print(f"    Procesando TAPA -> Pedido: {oc} | Línea: {ln} | TitleID: {tid}")
    ruta_orig = trabajo_actual['ruta_archivo_tapa_original']
    doc = None
    try:
        doc = fitz.open(ruta_orig)
        cajas = obtener_cajas_normalizadas_pypdf(ruta_orig)
        if not cajas: 
            doc.close()
            return None
        trim = cajas['trim']
        laminado = trabajo_actual.get('laminate')
        y_base = max(20, trim.y0-28)
        if laminado:
            doc[0].insert_text(fitz.Point(trim.x0, y_base), f"Laminado: {laminado}", fontsize=10)
        
        barcode_text = trabajo_actual.get('odoo_sale_order_name') or trabajo_actual.get('order_code')
        if barcode_text:
            try:
                import io
                from barcode import Code128
                from barcode.writer import ImageWriter
                buffer = io.BytesIO()
                Code128(barcode_text, writer=ImageWriter()).write(buffer, options={'write_text': False})
                
                # Subimos el código de barras bien arriba para alejarlo de la guillotina (mínimo y=2)
                y_top = max(2, trim.y0 - 35) 
                barcode_rect = fitz.Rect(trim.x0 + 150, y_top, trim.x0 + 150 + 150, y_top + 15)
                doc[0].insert_image(barcode_rect, stream=buffer.getvalue(), keep_proportion=True)
            except Exception as e:
                print(f"      ADVERTENCIA: No se pudo insertar el código de barras en la tapa. Error: {e}")
        
        fw, fh = (trim.width + 2*BLEED_PTS)*MM_PER_POINT, (trim.height + 2*BLEED_PTS)*MM_PER_POINT
        ps = ""
        if (fw<=320 and fh<=350) or (fh<=320 and fw<=350): ps = "33x36"
        elif (fw<=320 and fh<=470) or (fh<=320 and fw<=470): ps = "33x48.7"
        elif (fw<=320 and fh<=690) or (fh<=320 and fw<=690): ps = "33x70"
        else: 
            doc.close()
            return None

        oc = limpiar_id(trabajo_actual['order_code'], 'PED')
        tit = re.sub(r'[\\/*?:"<>|]', "", trabajo_actual['title'])[:50]
        nom = f"{oc}-{trabajo_actual['line_number']}_{ps}x{trabajo_actual['quantity_requested']}_{tit}.pdf"
        ruta_f = os.path.join(mapeos.DEST_PATH_TAPAS, nom)
        doc.save(ruta_f)
        doc.close()
        return ruta_f
    except Exception as e:
        print(f"      ERROR procesando tapa: {e}")
        if doc: doc.close()
        return None

def run():
    if not mapeos.PROCESAR_PDF_ACTIVADO: return
    print("--- Script 7 (TAPA) ---")
    
    conn = None
    trabajos = []
    try:
        conn = db_conn.conectar_db()
        if conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' for _ in mapeos.ESTADOS_A_EXCLUIR_PRODUCCION)
            query = f"SELECT * FROM trabajos WHERE odoo_pickings_data_json IS NOT NULL AND estado_tapa_produccion = ? AND (line_status_id IS NULL OR line_status_id NOT IN ({placeholders}))"
            
            params = [mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE] + mapeos.ESTADOS_A_EXCLUIR_PRODUCCION
            cursor.execute(query, params)
            
            trabajos = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR en Script 7 al consultar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

    if not trabajos:
        return

    odoo_api = odoo_conn.conectar_odoo() if trabajos else None

    for t in trabajos:
        rt = t.get('ruta_trabajo')
        tid = limpiar_id(t.get('title_id', ''), 'PAP')
        if not rt:
            pids = [t.get('publisher_id'), t.get('publisher_facility')]
            rt = encontrar_ruta_trabajo_dinamicamente(mapeos.BASE_STORAGE_PATH, [p for p in pids if p], tid)
            if rt:
                conn = db_conn.conectar_db(); cursor = conn.cursor()
                cursor.execute("UPDATE trabajos SET ruta_trabajo = ? WHERE order_code = ? AND line_number = ?", (rt, t['order_code'], t['line_number']))
                conn.commit(); conn.close()

        if rt:
            r_orig, error_msg = encontrar_archivo_mas_reciente(rt, tid, 'TAPA', t.get('order_type', ''))
            if r_orig:
                t['ruta_archivo_tapa_original'] = r_orig
                res = procesar_tapa(t)
                if res:
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_tapa_produccion = 'GENERADO', ruta_archivo_tapa = ? WHERE order_code = ? AND line_number = ?", 
                                   (res, t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ✅ Tapa {t['order_code']} OK")
                    
                    # --- NOTIFICAR A ODOO ---
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            so.message_post(body=f"✅ **Producción Tapa:** Generada correctamente.\nArchivo: `{os.path.basename(res)}`")
                    except: pass
                else:
                    # Marcar como error en la DB para no trabar el loop
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_tapa_produccion = 'ERROR' WHERE order_code = ? AND line_number = ?", 
                                   (t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ❌ Error al procesar Tapa {t['order_code']}")
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            body = f"⚠️ **Producción Tapa:** Error al procesar archivo físico (medidas incorrectas o archivo dañado).\nTitleID: {tid}"
                            so.message_post(body=body)
                    except: pass
            else:
                # Notificar fallo detallado (no se encontró archivo apto, se mantiene en PENDIENTE)
                try:
                    if odoo_api and t.get('odoo_sale_order_id'):
                        so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                        body = f"⚠️ **Producción Tapa:** {error_msg}\nTitleID: {tid}"
                        so.message_post(body=body)
                except: pass

if __name__ == "__main__":
    run()
